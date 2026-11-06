#!/usr/bin/env ruby
# frozen_string_literal: true

require 'date'
require 'json'
require 'jekyll'
require 'nokogiri'
require 'optparse'
require 'open3'
require 'yaml'

ROOT = File.expand_path('..', __dir__)
POST = '_posts/2024/06/2024-06-05-aws-seminar.md'
CANONICAL = 'https://kkamji.net/posts/aws-seminar/'
EMBED = 'https://www.youtube.com/embed/i2Is1_b1Hgw'
VERIFIED_VIDEO = {
  '@context' => 'https://schema.org',
  '@type' => 'VideoObject',
  'thumbnailUrl' => 'https://i.ytimg.com/vi/i2Is1_b1Hgw/hqdefault.jpg',
  'uploadDate' => '2024-06-05T19:49:43-07:00',
  'duration' => 'PT17M32S',
  'embedUrl' => EMBED,
  'mainEntityOfPage' => CANONICAL
}.freeze
COVER_RULE = /article:has\(\.watch-video\)\s*>\s*header\s+\.post-meta\s*>\s*\.mt-3\.mb-3\s*\{\s*display:\s*none;?\s*\}/

options = {}
OptionParser.new do |parser|
  parser.on('--site PATH', 'Also inspect the production page and stylesheet') { |path| options[:site] = path }
  parser.on('--staged', 'Read the post and styles from the index') { options[:staged] = true }
end.parse!
abort 'Unexpected positional arguments' unless ARGV.empty?

read_input = lambda do |path|
  if options[:staged]
    content, error, status = Open3.capture3('git', 'show', ":#{path}", chdir: ROOT)
    abort error unless status.success?
    content
  else
    File.read(File.join(ROOT, path))
  end
end
source = read_input.call(POST)
match = source.match(/\A---\r?\n(.*?)\r?\n---\r?\n(.*)\z/m)
abort 'Missing source frontmatter' unless match
metadata = YAML.safe_load(match[1], permitted_classes: [Date, Time], aliases: false)
body = match[2]
failures = []
checks = 0
check = lambda do |label, passed|
  checks += 1
  failures << label unless passed
end
video = metadata['video']
check.call('source has VideoObject metadata', video.is_a?(Hash))
video ||= {}
VERIFIED_VIDEO.each { |key, value| check.call("provider-verified #{key}", video[key] == value) }
%w[name description].each { |key| check.call("nonempty video #{key}", video[key].is_a?(String) && !video[key].strip.empty?) }
check.call('page title identifies the presentation video', metadata['title'].include?('발표 영상'))
check.call('page description identifies the presentation video', metadata['description'].include?('영상'))
style = read_input.call('assets/css/jekyll-theme-chirpy.scss')
check.call('cover opt-out is scoped to an actual watch player', COVER_RULE.match?(style))

Liquid::Template.register_filter(Jekyll::Filters)
liquid = Liquid::Template.parse(body).render!({ 'page' => metadata }, strict_variables: true, strict_filters: true)
converter = Jekyll::Converters::Markdown.new(Jekyll.configuration('source' => ROOT, 'quiet' => true))
fragment = Nokogiri::HTML.fragment(converter.convert(liquid))

inspect_player = lambda do |document|
  issues = []
  players = document.css('.watch-video > iframe')
  issues << 'single prominent player' unless players.length == 1
  player = players.first
  if player
    issues << 'player uses the verified embed URL' unless player['src'] == EMBED
    issues << 'player has a meaningful title' if player['title'].to_s.strip.empty?
    issues << 'player is not lazy or click-injected' unless player['loading'] == 'eager'
    issues << 'playback is user initiated' if player['src'].include?('autoplay') || player['allow'].to_s.split(';').map(&:strip).include?('autoplay')
    prose = document.css('p').find { |node| node.text.start_with?('AWS 강의실 온라인 세미나에 참석하여') }
    issues << 'original retrospective is retained after the video' unless prose && (player <=> prose) == -1
  end
  schemas = document.css('script[type="application/ld+json"]').filter_map do |node|
    parsed = JSON.parse(node.text)
    parsed if parsed.is_a?(Hash) && parsed['@type'] == 'VideoObject'
  rescue JSON::ParserError
    issues << 'valid JSON-LD'
    nil
  end
  issues << 'single VideoObject' unless schemas.length == 1
  if schemas.length == 1
    video.each { |key, value| issues << "rendered #{key} matches source" unless schemas[0][key] == value }
  end
  issues
end

check.call('rendered source exposes a first-position player and matching VideoObject', inspect_player.call(fragment).empty?)
{
  'missing schema' => lambda { |doc| doc.css('script[type="application/ld+json"]').remove },
  'different embed' => lambda { |doc| doc.at_css('iframe')['src'] = 'https://www.youtube.com/embed/other_video' },
  'lazy player' => lambda { |doc| doc.at_css('iframe')['loading'] = 'lazy' },
  'autoplay' => lambda { |doc| doc.at_css('iframe')['src'] += '?autoplay=1' },
  'video after retrospective' => lambda do |doc|
    player = doc.at_css('.watch-video')
    prose = doc.css('p').find { |node| node.text.start_with?('AWS 강의실 온라인 세미나에 참석하여') }
    prose.add_next_sibling(player.remove)
  end,
  'invented duration' => lambda do |doc|
    node = doc.at_css('script[type="application/ld+json"]')
    data = JSON.parse(node.text)
    data['duration'] = 'PT1S'
    node.content = JSON.generate(data)
  end
}.each do |label, mutate|
  if inspect_player.call(fragment).empty?
    changed = fragment.dup
    mutate.call(changed)
    check.call("rejects #{label}", !inspect_player.call(changed).empty?)
  end
end

if options[:site]
  site = File.expand_path(options[:site])
  page = File.join(site, 'posts/aws-seminar/index.html')
  css = File.join(site, 'assets/css/jekyll-theme-chirpy.css')
  check.call('production watch page exists', File.file?(page))
  check.call('production stylesheet exists', File.file?(css))
  if File.file?(page) && File.file?(css)
    document = Nokogiri::HTML(File.read(page))
    issues = inspect_player.call(document)
    issues.each { |issue| failures << "production: #{issue}" }
    check.call('production player and schema', issues.empty?)
    check.call('production canonical URL is unchanged', document.at_css('link[rel="canonical"]')&.[]('href') == CANONICAL)
    check.call('cover selector still matches the theme header', !document.at_css('article > header .post-meta > .mt-3.mb-3 .preview-img').nil?)
    check.call('production CSS contains the scoped cover opt-out', COVER_RULE.match?(File.read(css)))
  end
end

puts "#{checks} checks, #{failures.length} failures"
failures.each { |failure| warn "FAIL: #{failure}" }
exit(failures.empty? ? 0 : 1)
