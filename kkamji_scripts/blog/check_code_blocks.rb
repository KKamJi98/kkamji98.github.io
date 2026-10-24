# frozen_string_literal: true

require 'json'
require 'optparse'
require 'open3'
require 'kramdown'
require 'kramdown-parser-gfm'
require 'nokogiri'
require 'jekyll'
require_relative '../../_plugins/code-highlighting'

module BlogCodeBlocks
  # Kramdown has already stripped list/quote prefixes when it calls this hook.
  # Opaque HTML, escaped text and inner examples never enter it as new fences.
  class FenceParser < Kramdown::Parser::GFM
    def parse_codeblock_fenced
      opening = @src.check(/^ {0,3}(`{3,}|~{3,})[^\n]*\n/)
      marker = opening&.match(/(`{3,}|~{3,})/)&.[](1)
      line = @src.current_line_number
      parsed = super
      issues = (@root.options[:fence_findings] ||= [])
      if marker && !parsed
        issues << { line: line, issue: 'unclosed-fence' }
      elsif marker
        @tree.children.last.value.each_line.with_index do |text, index|
          if text.match?(/\A {0,3}#{Regexp.escape(marker[0])}{#{marker.length},}[a-zA-Z][a-zA-Z0-9_+-]*[ \t]*\n?\z/)
            issues << { line: line + index + 1, issue: 'nested-fence-with-language' }
          end
        end
      end
      parsed
    end
  end

  def self.inspect_code(code, language, location)
    return [location.merge(issue: 'automatic-language')] if language.split('?', 2).first == 'guess'

    lexer = Rouge::Lexer.find_fancy(language, code || '')
    return [location.merge(issue: 'unknown-language')] unless lexer
    return [] unless code # Dynamic Liquid bodies are checked only after the production build.

    tokens = lexer.lex(code).to_a
    findings = []
    findings << location.merge(issue: 'lexer-error') if tokens.any? { |token, _| token == Rouge::Token['Error'] }
    findings << location.merge(issue: 'source-text-changed') unless tokens.map(&:last).join == code
    findings
  end

  def self.inspect_highlights(body, path, offset)
    count = 0
    findings = []
    return { blocks: count, findings: findings } unless body.match?(/\{%[-]?\s*highlight\s/)

    # Parse only: never evaluate repository Liquid, includes or variables.
    walk = lambda do |node|
      next if node.is_a?(Liquid::Comment) || node.is_a?(Liquid::Raw)

      if node.is_a?(Jekyll::Tags::HighlightBlock)
        count += 1
        language = node.instance_variable_get(:@lang)
        if node.nodelist.all? { |part| part.is_a?(String) }
          code = node.nodelist.join.gsub(Jekyll::Tags::HighlightBlock::LEADING_OR_TRAILING_LINE_TERMINATORS, '')
        end
        location = { path: path, line: node.line_number + offset, language: language }
        findings.concat(inspect_code(code, language, location))
      elsif node.respond_to?(:nodelist)
        Array(node.nodelist).each { |child| walk.call(child) }
      end
    end
    walk.call(Liquid::Template.parse(body, line_numbers: true).root)
    { blocks: count, findings: findings }
  rescue Liquid::SyntaxError, ::SyntaxError => error
    line = error.respond_to?(:line_number) && error.line_number || 1
    findings << { path: path, line: line + offset, issue: 'liquid-parse-error' }
    { blocks: count, findings: findings }
  end

  def self.inspect_source(source, path)
    body = source.sub(/\A---[^\S\n]*\r?\n.*?\r?\n---[^\S\n]*\r?\n/m, '')
    offset = source.lines.length - body.lines.length
    count = 0
    root, = FenceParser.parse(body)
    findings = Array(root.options[:fence_findings]).map do |row|
      { path: path, line: row[:line] + offset, issue: row[:issue] }
    end
    walk = lambda do |node|
      if node.type == :codeblock
        count += 1
        language = node.options[:lang] || 'text'
        location = { path: path, line: node.options.fetch(:location, 1) + offset, language: language }
        findings.concat(inspect_code(node.value, language, location))
      end
      node.children.each { |child| walk.call(child) }
    end
    walk.call(root)
    highlights = inspect_highlights(body, path, offset)
    { blocks: count + highlights[:blocks], findings: findings + highlights[:findings] }
  end

  def self.inspect_html(html, path)
    doc = Nokogiri::HTML(html)
    findings = []
    blocks = doc.css('div.highlighter-rouge, figure.highlight')
    blocks.each_with_index do |block, index|
      location = { path: path, block: index + 1 }
      findings << location.merge(issue: 'rendered-lexer-error') unless block.css('.err').empty?
      code = block.at_css('code')
      classes = [block, code].compact.flat_map { |node| node['class'].to_s.split }
      language = code&.[]('data-lang') || classes.filter_map do |name|
        name.delete_prefix('language-') if name.start_with?('language-')
      end.first
      if language&.split('?', 2)&.first == 'guess'
        findings << location.merge(issue: 'rendered-automatic-language', language: language)
      elsif language && !Rouge::Lexer.find(language)
        findings << location.merge(issue: 'rendered-unknown-language', language: language)
      end
    end
    { blocks: blocks.length, findings: findings }
  end

  def self.run(arguments)
    options = { root: Dir.pwd }
    parser = OptionParser.new do |opts|
      opts.banner = 'Usage: bundle exec ruby kkamji_scripts/blog/check_code_blocks.rb [--staged] [--site DIR] [--report FILE] [POST ...]'
      opts.on('--root DIR') { |value| options[:root] = value }
      opts.on('--staged', 'Read authored Markdown bytes from the Git index') { options[:staged] = true }
      opts.on('--site DIR', 'Inspect production HTML instead of Markdown') { |value| options[:site] = value }
      opts.on('--report FILE') { |value| options[:report] = value }
    end
    paths = parser.parse(arguments)
    root = File.realpath(options[:root])
    raise ArgumentError, '--staged cannot be combined with --site or file paths' if options[:staged] && (options[:site] || !paths.empty?)
    raise ArgumentError, '--site cannot be combined with file paths' if options[:site] && !paths.empty?

    if options[:site]
      site = File.realpath(options[:site])
      paths = Dir.glob(File.join(site, '**', '*.html')).sort
      raise ArgumentError, 'No rendered HTML files found' if paths.empty?
      inputs = paths.map { |path| [path.delete_prefix(site + '/'), File.read(path, encoding: 'UTF-8')] }
      inspect_method = method(:inspect_html)
    elsif options[:staged]
      tracked, status = Open3.capture2('git', 'ls-files', '--stage', '-z', '--', '_posts', '_tabs', 'docs', 'kkamji_scripts', 'README.md', 'AGENTS.md', chdir: root)
      raise ArgumentError, 'Cannot read Git index' unless status.success?
      entries = tracked.split("\0").filter_map do |row|
        metadata, path = row.split("\t", 2)
        next unless path&.match?(/\.(md|markdown)\z/)
        mode, oid, stage = metadata.split
        raise ArgumentError, "Unmerged or non-regular source: #{path}" unless stage == '0' && %w[100644 100755].include?(mode)
        [path, oid]
      end
      data, status = Open3.capture2('git', 'cat-file', '--batch', chdir: root,
                                   stdin_data: entries.map(&:last).join("\n") + "\n")
      raise ArgumentError, 'Cannot read staged source blobs' unless status.success?
      data = data.b
      cursor = 0
      inputs = entries.map do |path, expected_oid|
        header_end = data.index("\n", cursor)
        raise ArgumentError, "Missing staged source: #{path}" unless header_end
        oid, type, size = data.byteslice(cursor...header_end).split
        raise ArgumentError, "Invalid staged blob: #{path}" unless oid == expected_oid && type == 'blob' && size&.match?(/\A\d+\z/)
        cursor = header_end + 1
        source = data.byteslice(cursor, size.to_i)
        cursor += size.to_i
        raise ArgumentError, "Truncated staged blob: #{path}" unless source&.bytesize == size.to_i && data.byteslice(cursor, 1) == "\n"
        cursor += 1
        [path, source.force_encoding('UTF-8')]
      end
      inspect_method = method(:inspect_source)
    else
      if paths.empty?
        paths = Dir.glob(File.join(root, '{_posts,_tabs,docs,kkamji_scripts}', '**', '*.{md,markdown}'))
        paths += %w[README.md AGENTS.md].map { |path| File.join(root, path) }.select { |path| File.file?(path) }
        paths.sort!
      end
      inputs = paths.map do |path|
        full = File.realpath(File.expand_path(path, root))
        raise ArgumentError, "Source path is outside root: #{path}" unless full.start_with?(root + '/')
        [full.delete_prefix(root + '/'), File.read(full, encoding: 'UTF-8')]
      end
      inspect_method = method(:inspect_source)
    end
    raise ArgumentError, 'No source documents found' if inputs.empty?
    results = inputs.map { |path, source| inspect_method.call(source, path) }
    report = { mode: options[:site] ? 'rendered' : options[:staged] ? 'staged' : 'source',
               rouge: Rouge.version, documents: inputs.length, blocks: results.sum { |row| row[:blocks] },
               findings: results.flat_map { |row| row[:findings] } }
    File.write(options[:report], JSON.pretty_generate(report) + "\n") if options[:report]
    report[:findings].each { |row| warn "#{row[:path]}:#{row[:line] || row[:block]}: #{row[:issue]} (#{row[:language] || 'rendered'})" }
    puts "Code blocks (#{report[:mode]}): #{report[:documents]} documents, #{report[:blocks]} blocks, #{report[:findings].length} findings; Rouge #{report[:rouge]}"
    report[:findings].empty? ? 0 : 1
  rescue OptionParser::ParseError, ArgumentError, Errno::ENOENT => error
    warn error.message
    2
  end
end

exit BlogCodeBlocks.run(ARGV) if $PROGRAM_NAME == __FILE__
