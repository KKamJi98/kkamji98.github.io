# frozen_string_literal: true

require 'json'
require 'cgi'

module Jekyll
  class DiagramPostMap < Generator
    safe true
    priority :low

    def generate(site)
      manifest = File.join(site.source, 'docs', 'diagram-downloads.json')
      return unless File.file?(manifest)

      entries = JSON.parse(File.read(manifest)).fetch('entries')
      covers = site.posts.docs.select do |post|
        image = post.data['image']
        path = image.is_a?(Hash) ? image['path'] : image
        path.is_a?(String) && path.start_with?('/assets/img/diagrams/')
      end.map { |post| post.relative_path.delete_prefix('/') }
      wanted = (entries.map { |entry| entry.fetch('post') } + covers).uniq
      posts = site.posts.docs.to_h { |post| [post.relative_path.delete_prefix('/'), post.url] }
      missing = wanted - posts.keys
      raise "Diagram source posts missing: #{missing.join(', ')}" unless missing.empty?

      page = PageWithoutAFile.new(site, site.source, 'assets/data', 'diagram-posts.json')
      page.data['layout'] = nil
      page.data['sitemap'] = false
      page.content = JSON.pretty_generate(wanted.sort.to_h { |path| [path, posts.fetch(path)] }) + "\n"
      site.pages << page
      entries.each { |entry| generate_viewer(site, entry, posts) }
      generate_proof_fixture(site) if ENV['DIAGRAM_FHD_PROOF'] == '1'
    end

    def generate_viewer(site, entry, posts)
      png = entry.fetch('png')
      legacy = !png.start_with?('/assets/img/diagrams/native-updates/') &&
        png.match?(%r{\A/assets/img/diagrams/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+--[a-f0-9]{16}\.png\z})
      update = false
      update_file = File.join(site.source, 'docs', 'diagram-native-update.json')
      if png.match?(%r{\A/assets/img/diagrams/native-updates/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+\.png\z}) && File.file?(update_file)
        declaration = JSON.parse(File.read(update_file))
        update = declaration['schema'] == 1 && declaration['status'] == 'fresh-native-update-reviewed' &&
          declaration.fetch('sources').any? do |record|
            next false unless record.is_a?(Hash) && record['include'] == entry['include']
            baseline = JSON.parse(File.read(File.join(site.source, 'docs', 'diagram-export-release.json')))
            all_archived = baseline.fetch('entries') + baseline.fetch('unused_entries', [])
            archived = all_archived.select { |row| row['include'] == record['include'] }
            occurrences = record['occurrences']
            unless record.key?('occurrences')
              occurrences = archived.length == 1 ? [archived.first.merge('old_png' => record['old_png'], 'new_png' => record['new_png'])] : []
            end
            next false unless occurrences.is_a?(Array) && !occurrences.empty? && occurrences.length == archived.length
            originals = occurrences.map { |row| row.is_a?(Hash) && row['old_png'] }
            destinations = occurrences.map { |row| row.is_a?(Hash) && row['new_png'] }
            next false unless originals.uniq.length == originals.length && destinations.uniq.length == destinations.length &&
              originals.sort == archived.map { |row| row.fetch('png') }.sort &&
              (destinations & all_archived.map { |row| row.fetch('png') }).empty? &&
              occurrences.any? { |row| row['old_png'] == record['old_png'] && row['new_png'] == record['new_png'] }
            next false unless occurrences.all? do |occurrence|
              original = archived.find { |row| row['png'] == occurrence['old_png'] }
              original && %w[post figure].all? { |key| original[key].is_a?(String) && occurrence[key] == original[key] } &&
                occurrence['old_png'].to_s.match?(%r{\A/assets/img/diagrams/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+--[a-f0-9]{16}\.png\z}) &&
                occurrence['new_png'].to_s.match?(%r{\A/assets/img/diagrams/native-updates/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+\.png\z})
            end
            occurrences.any? do |occurrence|
              %w[post figure old_png].all? { |key| occurrence[key] == entry[key] } && occurrence['new_png'] == png
            end
          end
      end
      unless legacy || update
        raise "Invalid diagram viewer PNG path: #{png}"
      end
      path = png.delete_prefix('/assets/img/diagrams/').sub(/\.png\z/, '.html')
      include_path = File.join(site.source, '_includes', entry.fetch('include'))
      caption = File.read(include_path)[%r{<figcaption[^>]*>(.*?)</figcaption>}m, 1]
      title = CGI.escapeHTML(CGI.unescapeHTML(caption.to_s.gsub(/<[^>]*>/, '').strip))
      base = site.config.fetch('baseurl', '').to_s
      webp_url = CGI.escapeHTML(base + png.sub(/\.png\z/, '.webp'))
      post_url = CGI.escapeHTML(base + posts.fetch(entry.fetch('post')) + '#' + entry.fetch('figure'))
      page = PageWithoutAFile.new(site, site.source, File.join('diagrams/view', File.dirname(path)), File.basename(path))
      page.data['layout'] = nil
      page.data['sitemap'] = false
      page.content = <<~HTML
        <!doctype html>
        <html lang="ko"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="robots" content="noindex"><title>#{title} - 다이어그램 확대 보기</title>
        <style>
          :root { color-scheme: light; font-family: system-ui, sans-serif; background: #fff; color: #172033; }
          body { margin: 0; padding: 16px; }
          h1 { font-size: 20px; margin: 0 0 12px; }
          nav { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 16px; }
          a { color: #075985; }
          .zoom-target { position: absolute; width: 1px; height: 1px; overflow: hidden; }
          .diagram-viewport { overflow: auto; width: 100%; max-height: calc(100vh - 160px); border: 1px solid #cbd5e1; }
          .diagram-space { width: 1920px; height: 1080px; }
          .diagram-canvas { display: block; width: 1920px; min-width: 1920px; max-width: 1920px; height: 1080px; min-height: 1080px; max-height: 1080px; transform-origin: top left; }
          #zoom-125:target ~ .diagram-viewport .diagram-space { width: 2400px; height: 1350px; }
          #zoom-125:target ~ .diagram-viewport .diagram-canvas { transform: scale(1.25); }
          #zoom-150:target ~ .diagram-viewport .diagram-space { width: 2880px; height: 1620px; }
          #zoom-150:target ~ .diagram-viewport .diagram-canvas { transform: scale(1.5); }
        </style></head><body>
          <span class="zoom-target" id="zoom-100"></span><span class="zoom-target" id="zoom-125"></span><span class="zoom-target" id="zoom-150"></span>
          <h1>#{title}</h1>
          <nav aria-label="다이어그램 확대 및 다운로드"><a href="#zoom-100">100%</a><a href="#zoom-125">125%</a><a href="#zoom-150">150%</a><a href="#{webp_url}" download>WebP 다운로드</a><a href="#{post_url}">본문으로 돌아가기</a></nav>
          <p>기본 크기는 1920 x 1080입니다. 좁은 화면에서는 스크롤하고, 확대 비율은 직접 선택하세요.</p>
          <div class="diagram-viewport" tabindex="0" role="region" aria-label="스크롤 가능한 고정 크기 다이어그램">
            <div class="diagram-space"><img class="diagram-canvas" src="#{webp_url}" width="1920" height="1080" alt="#{title}"></div>
          </div>
        </body></html>
      HTML
      site.pages << page
    end

    # This fixture is emitted only in the isolated verification build. It uses
    # the same SVG files as the canonical figures, without a second layout.
    def generate_proof_fixture(site)
      catalog = JSON.parse(File.read(File.join(site.source, 'docs/diagram-catalog.json'))).fetch('diagrams')
      cards = catalog.each_with_index.map do |record, index|
        relative = record.fetch('include').delete_prefix('diagrams/').sub(/\.html\z/, '.svg')
        svg = File.read(File.join(site.source, 'assets/img/diagrams/fhd-svg', relative))
        name = CGI.escapeHTML(record.fetch('include'))
        "<section class=\"proof-card\" data-index=\"#{index}\" data-include=\"#{name}\"><h2>#{name}</h2>#{svg}</section>"
      end.join("\n")
      page = PageWithoutAFile.new(site, site.source, 'diagrams/fhd-proof', 'index.html')
      page.data['layout'] = nil
      page.data['sitemap'] = false
      page.content = <<~HTML
        <!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><title>FHD diagram verification</title>
        <style>@font-face{font-family:"SD FHD Sans";src:url("/assets/fonts/deterministic-export/NotoSansKR[wght].ttf") format("truetype");font-weight:100 900}body{margin:0;color:#172033;background:#fff;font-family:system-ui,sans-serif}h2{font-size:16px}section{overflow:visible}svg.sd-fhd-artwork{display:block;width:1920px;min-width:1920px;max-width:1920px;height:1080px;min-height:1080px;max-height:1080px;font-family:"SD FHD Sans"}svg text{font-family:"SD FHD Sans"}</style></head><body>
        <h1 id="proof-index">#{catalog.length} fixed FHD diagrams</h1>
        <a id="proof-font" href="/assets/fonts/deterministic-export/NotoSansKR[wght].ttf">Pinned diagram font</a>
        #{cards}</body></html>
      HTML
      site.pages << page
    end
  end
end
