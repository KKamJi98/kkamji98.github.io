# frozen_string_literal: true

require_relative '../kkamji_scripts/blog/check_post_descriptions'

Jekyll::Hooks.register :site, :post_read do |site|
  sources = []
  findings = []
  site.posts.docs.each do |post|
    begin
      source, errors = BlogPostDescriptions.parse_source(File.read(post.path, encoding: 'UTF-8'), post.relative_path)
      findings.concat(errors)
      sources << [post, source] if source
    rescue SystemCallError
      findings << { path: post.relative_path, issue: 'source-description-read-error' }
    end
  end
  findings.concat(BlogPostDescriptions.inspect_documents(sources.map(&:last)))
  unless findings.empty?
    messages = findings.map { |row| "#{row[:path]}: #{row[:issue]}" }
    raise Jekyll::Errors::FatalException, "Post description validation failed:\n#{messages.join("\n")}"
  end
  sources.each do |post, source|
    post.instance_variable_set(:@blog_source_description, source.data.fetch('description').dup.freeze)
  end
end

Jekyll::Hooks.register :posts, :post_render do |post|
  description = post.instance_variable_get(:@blog_source_description)
  if description.nil?
    raise Jekyll::Errors::FatalException, "#{post.relative_path}: missing-source-description-snapshot"
  end
  unless post.data['description'] == description
    raise Jekyll::Errors::FatalException, "#{post.relative_path}: description-changed-from-source"
  end
  markdown = post.site.find_converter_instance(Jekyll::Converters::Markdown).convert(description)
  seo_expected = BlogPostDescriptions.normalize(Nokogiri::HTML.fragment(markdown).text)
  findings = BlogPostDescriptions.inspect_html(post.output, description, post.relative_path, seo_expected: seo_expected)
  unless findings.empty?
    messages = findings.map { |row| "#{row[:path]}: #{row[:issue]}" }
    raise Jekyll::Errors::FatalException, "Rendered post description validation failed:\n#{messages.join("\n")}"
  end
end
