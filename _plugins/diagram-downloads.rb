# frozen_string_literal: true

require 'json'

module Jekyll
  class DiagramPostMap < Generator
    safe true
    priority :low

    def generate(site)
      manifest = File.join(site.source, 'docs', 'diagram-downloads.json')
      return unless File.file?(manifest)

      wanted = JSON.parse(File.read(manifest)).fetch('entries').map { |entry| entry.fetch('post') }.uniq
      posts = site.posts.docs.to_h { |post| [post.relative_path.delete_prefix('/'), post.url] }
      missing = wanted - posts.keys
      raise "Diagram source posts missing: #{missing.join(', ')}" unless missing.empty?

      page = PageWithoutAFile.new(site, site.source, 'assets/data', 'diagram-posts.json')
      page.data['layout'] = nil
      page.data['sitemap'] = false
      page.content = JSON.pretty_generate(wanted.sort.to_h { |path| [path, posts.fetch(path)] }) + "\n"
      site.pages << page
    end
  end
end
