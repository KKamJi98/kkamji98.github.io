# frozen_string_literal: true

require 'date'
require 'json'
require 'open3'
require 'optparse'
require 'yaml'
require 'nokogiri'
require 'kramdown'
require 'kramdown-parser-gfm'

module BlogPostDescriptions
  MIN_LENGTH = 40
  MAX_LENGTH = 160
  SourcePost = Struct.new(:relative_path, :data)

  def self.inspect_documents(posts)
    return [{ path: '_posts', issue: 'no-posts' }] if posts.empty?

    findings = []
    descriptions = Hash.new { |hash, key| hash[key] = [] }
    posts.each do |post|
      location = { path: post.relative_path }
      value = post.data['description']
      unless value.is_a?(String) && value.valid_encoding? && !value.strip.empty?
        findings << location.merge(issue: 'missing-or-invalid-description')
        next
      end

      findings << location.merge(issue: 'description-length') unless (MIN_LENGTH..MAX_LENGTH).cover?(value.length)
      findings << location.merge(issue: 'description-whitespace') unless value == value.strip
      findings << location.merge(issue: 'description-control-character') if value.match?(/[\p{Cc}\p{Zl}\p{Zp}]/)
      if markup?(value)
        findings << location.merge(issue: 'description-markup')
      end
      if value.match?(/[\u00b7\u2192\u2010-\u2015\u2018-\u201f\u2026]/) ||
         value.each_char.any? { |character| character.ord > 127 && character.match?(/\p{P}/) }
        findings << location.merge(issue: 'description-punctuation')
      end
      if normalize(value).downcase == normalize(post.data['title'].to_s).downcase
        findings << location.merge(issue: 'description-repeats-title')
      end
      descriptions[normalize(value)] << post.relative_path
    end
    descriptions.each_value do |paths|
      next if paths.length == 1

      paths.each { |path| findings << { path: path, issue: 'duplicate-description' } }
    end
    findings
  end

  def self.markup?(value)
    return true if value.match?(/[<>`]|\{[{%]|\}\}|!?\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])/)

    nodes = [Kramdown::Document.new(value, input: 'GFM').root]
    until nodes.empty?
      node = nodes.pop
      return true unless %i[root p text smart_quote typographic_sym].include?(node.type)

      nodes.concat(node.children)
    end
    false
  end

  def self.normalize(value)
    value.to_s.gsub(/[[:space:]]+/, ' ').strip
  end

  def self.article_nodes(value)
    case value
    when Hash
      own = (Array(value['@type']) & %w[Article BlogPosting NewsArticle TechArticle]).empty? ? [] : [value]
      own + value.values.flat_map { |child| article_nodes(child) }
    when Array
      value.flat_map { |child| article_nodes(child) }
    else
      []
    end
  end

  def self.inspect_html(html, expected, path, seo_expected: expected)
    document = Nokogiri::HTML(html)
    findings = []
    {
      'seo-description' => 'meta[name="description"]',
      'open-graph-description' => 'meta[property="og:description"]',
      'twitter-description' => 'meta[name="twitter:description"], meta[property="twitter:description"]'
    }.each do |kind, selector|
      nodes = document.css(selector)
      unless nodes.length == 1 && normalize(nodes.first['content']) == normalize(seo_expected)
        findings << { path: path, issue: "rendered-#{kind}" }
      end
    end
    subtitles = document.css('.post-desc')
    unless subtitles.length == 1 && normalize(subtitles.first.text) == normalize(expected)
      findings << { path: path, issue: 'rendered-subtitle' }
    end

    begin
      articles = document.css('script[type="application/ld+json"]').flat_map do |node|
        article_nodes(JSON.parse(node.text))
      end
      unless !articles.empty? && articles.all? { |node| normalize(node['description']) == normalize(seo_expected) }
        findings << { path: path, issue: 'rendered-structured-description' }
      end
    rescue JSON::ParserError
      findings << { path: path, issue: 'rendered-structured-description' }
    end
    findings
  end

  def self.parse_source(text, path)
    match = text.match(/\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\z)/m)
    return [nil, [{ path: path, issue: 'missing-frontmatter' }]] unless match

    data = YAML.safe_load(match[1], permitted_classes: [Date, Time], aliases: false)
    unless data.is_a?(Hash) && data.keys.all? { |key| key.is_a?(String) }
      return [nil, [{ path: path, issue: 'invalid-frontmatter' }]]
    end

    mapping = Psych.parse(match[1]).root
    keys = mapping.children.each_slice(2).map { |key, _value| key.value }
    findings = []
    findings << { path: path, issue: 'duplicate-description-key' } if keys.count('description') > 1
    [SourcePost.new(path, data), findings]
  rescue Psych::Exception
    [nil, [{ path: path, issue: 'invalid-frontmatter' }]]
  end

  def self.run(arguments)
    options = { root: Dir.pwd, staged: false }
    OptionParser.new do |parser|
      parser.banner = 'Usage: bundle exec ruby kkamji_scripts/blog/check_post_descriptions.rb [--root DIR] [--staged]'
      parser.on('--root DIR') { |value| options[:root] = value }
      parser.on('--staged', 'Read the complete post collection from the Git index') { options[:staged] = true }
    end.parse!(arguments)
    raise ArgumentError, 'Unexpected positional arguments' unless arguments.empty?

    root = File.realpath(options[:root])
    tracked, status = Open3.capture2('git', 'ls-files', '-z', '--', '_posts', chdir: root)
    raise ArgumentError, 'Cannot enumerate tracked posts' unless status.success?

    paths = tracked.split("\0").select { |path| path.match?(/\.(md|markdown|html)\z/i) }.sort
    posts = []
    findings = []
    paths.each do |path|
      if options[:staged]
        text, read_status = Open3.capture2('git', 'show', ":#{path}", chdir: root)
        raise ArgumentError, "Cannot read staged post: #{path}" unless read_status.success?
      else
        begin
          text = File.read(File.join(root, path), encoding: 'UTF-8')
        rescue Errno::ENOENT
          findings << { path: path, issue: 'missing-source-file' }
          next
        end
      end
      post, errors = parse_source(text, path)
      posts << post if post
      findings.concat(errors)
    end
    findings.concat(inspect_documents(posts))
    findings.each { |row| warn "#{row[:path]}: #{row[:issue]}" }
    puts "Post descriptions: #{paths.length} posts, #{findings.length} findings"
    findings.empty? ? 0 : 1
  rescue ArgumentError, OptionParser::ParseError => error
    warn error.message
    2
  end
end

exit BlogPostDescriptions.run(ARGV) if $PROGRAM_NAME == __FILE__
