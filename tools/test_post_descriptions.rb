# frozen_string_literal: true

require 'cgi'
require 'json'
require 'fileutils'
require 'rbconfig'
require 'tmpdir'
require 'shellwords'
require_relative '../kkamji_scripts/blog/check_post_descriptions'

failures = []
checks = 0
assert = lambda do |label, &test|
  checks += 1
  failures << label unless test.call
end

description = '고정된 기본 가중치와 작은 보정 행렬로 학습할 파라미터를 줄이는 LoRA의 원리, 파라미터 계산, 병합 및 QLoRA와 RAG의 차이를 설명합니다.'
Document = Struct.new(:relative_path, :data)
post = lambda do |path, value, title = '기술 개념과 구현'|
  Document.new(path, { 'title' => title, 'description' => value })
end
issues = lambda do |value|
  BlogPostDescriptions.inspect_documents([post.call('_posts/example.md', value)]).map { |row| row[:issue] }
end

assert.call('LoRA-style Korean descriptions are accepted') { issues.call(description).empty? }
[nil, '', '   ', false, [], {}].each do |value|
  assert.call("Missing and non-string descriptions fail: #{value.inspect}") do
    issues.call(value).include?('missing-or-invalid-description')
  end
end
[40, 160].each do |length|
  assert.call("The #{length}-character boundary counts Unicode characters") { issues.call('가' * length).empty? }
end
[39, 161].each do |length|
  assert.call("Descriptions outside the length boundary fail: #{length}") do
    issues.call('가' * length).include?('description-length')
  end
end
assert.call('Whitespace around a description cannot silently become a different snippet') do
  issues.call(" #{description}").include?('description-whitespace')
end
assert.call('Folded prose must resolve to one line without control characters') do
  ["#{description}\n내용", "#{description}\t내용", "#{description}\u0000"].all? do |value|
    issues.call(value).include?('description-control-character')
  end
end
['<b>설명</b>', '**강조**', '`명령`', '[문서](https://example.com)', '{{ page.title }}', '{% include title.html %}'].each do |markup|
  assert.call("Descriptions reject display markup: #{markup}") do
    issues.call("#{description} #{markup}").include?('description-markup')
  end
end
['*강조*', '_강조_', '[문서][참조]'].each do |markup|
  assert.call("Inline Markdown cannot enter a plain-text description: #{markup}") do
    issues.call("#{description} #{markup}").include?('description-markup')
  end
end
assert.call('Plain technical identifiers and file globs are not Markdown') do
  issues.call('user_data.tpl과 C++, --env-file, @Transactional의 표기를 유지하고 관련 설정과 호출 경계를 설명합니다. 파일 선택에는 *.md 패턴을 사용합니다.').empty?
end
[0x00b7, 0x2192, 0x2014, 0x201c, 0x2026].each do |codepoint|
  assert.call("Authored punctuation stays ASCII: U+#{codepoint.to_s(16)}") do
    issues.call("#{description} #{codepoint.chr(Encoding::UTF_8)}").include?('description-punctuation')
  end
end
[0xff0c, 0x2022].each do |codepoint|
  assert.call("All authored non-ASCII punctuation fails: U+#{codepoint.to_s(16)}") do
    issues.call("#{description} #{codepoint.chr(Encoding::UTF_8)}").include?('description-punctuation')
  end
end
[0x2028, 0x2029].each do |codepoint|
  assert.call("Unicode line boundaries fail: U+#{codepoint.to_s(16)}") do
    issues.call("#{description}#{codepoint.chr(Encoding::UTF_8)}내용").include?('description-control-character')
  end
end
assert.call('A description cannot merely repeat the title') do
  rows = BlogPostDescriptions.inspect_documents([post.call('_posts/example.md', description, description)])
  rows.any? { |row| row[:issue] == 'description-repeats-title' }
end
assert.call('Two posts cannot share one generic description') do
  rows = BlogPostDescriptions.inspect_documents([
    post.call('_posts/first.md', description), post.call('_posts/second.md', description)
  ])
  rows.count { |row| row[:issue] == 'duplicate-description' } == 2
end
assert.call('An empty post collection fails closed') do
  BlogPostDescriptions.inspect_documents([]).any? { |row| row[:issue] == 'no-posts' }
end

render = lambda do |value|
  escaped = CGI.escapeHTML(value)
  <<~HTML
    <!doctype html><html><head>
    <meta name="description" content="#{escaped}">
    <meta property="og:description" name="twitter:description" content="#{escaped}">
    <script type="application/ld+json">#{JSON.generate({ '@type' => 'BlogPosting', 'description' => value })}</script>
    </head><body><article><p class="post-desc">#{escaped}</p></article></body></html>
  HTML
end
html_issues = lambda do |html, expected = description|
  BlogPostDescriptions.inspect_html(html, expected, 'example.html').map { |row| row[:issue] }
end
html = render.call(description)
assert.call('Rendered subtitle, SEO, Open Graph, Twitter and JSON-LD match') { html_issues.call(html).empty? }
special = 'A & B, "quoted" 설정과 QLoRA의 차이를 비교하고 작은 보정 행렬의 학습 대상과 메모리 조건을 설명합니다.'
assert.call('HTML entities are decoded exactly once for comparisons') do
  html_issues.call(render.call(special), special).empty?
end
{
  'seo' => /<meta name="description"[^>]*>/,
  'open-graph' => /<meta property="og:description"[^>]*>/,
  'subtitle' => /<p class="post-desc">.*?<\/p>/,
  'structured-data' => /<script type="application\/ld\+json">.*?<\/script>/
}.each do |name, pattern|
  assert.call("Missing #{name} cannot pass rendered verification") do
    !html_issues.call(html.sub(pattern, '')).empty?
  end
end
assert.call('Twitter metadata may be a separate node') do
  split = html.sub('property="og:description" name="twitter:description"', 'property="og:description"')
  split = split.sub('</head>', "<meta name=\"twitter:description\" content=\"#{CGI.escapeHTML(description)}\"></head>")
  html_issues.call(split).empty?
end
assert.call('Missing Twitter metadata fails independently from Open Graph') do
  html_issues.call(html.sub(' name="twitter:description"', '')).include?('rendered-twitter-description')
end
assert.call('An obsolete generated excerpt cannot replace the authored subtitle') do
  changed = html.sub("<p class=\"post-desc\">#{CGI.escapeHTML(description)}</p>", '<p class="post-desc">자동 발췌</p>')
  html_issues.call(changed).include?('rendered-subtitle')
end
assert.call('Conflicting duplicate metadata fails') do
  changed = html.sub('</head>', '<meta name="description" content="다른 내용"></head>')
  html_issues.call(changed).include?('rendered-seo-description')
end
assert.call('Malformed JSON-LD fails without leaking its contents') do
  changed = html.sub(/<script type="application\/ld\+json">.*?<\/script>/, '<script type="application/ld+json">{bad}</script>')
  html_issues.call(changed).include?('rendered-structured-description')
end
assert.call('A mismatched article description inside JSON-LD fails') do
  changed = html.sub('"description":' + JSON.generate(description), '"description":"다른 내용"')
  html_issues.call(changed).include?('rendered-structured-description')
end
assert.call('Unrelated JSON-LD is not an article description') do
  changed = html.sub('"@type":"BlogPosting"', '"@type":"Organization"')
  html_issues.call(changed).include?('rendered-structured-description')
end

source = "---\ntitle: Example\ndescription: #{JSON.generate(description)}\ndate: 2026-11-06 12:00:00 +0900\n---\n\nBody.\n"
assert.call('Timestamp frontmatter keeps a literal description') do
  parsed, errors = BlogPostDescriptions.parse_source(source, 'example.md')
  errors.empty? && parsed.data['description'] == description
end
assert.call('Duplicate description keys cannot silently overwrite one another') do
  changed = source.sub('date:', "description: #{JSON.generate(description)}\ndate:")
  _, errors = BlogPostDescriptions.parse_source(changed, 'example.md')
  errors.any? { |row| row[:issue] == 'duplicate-description-key' }
end
assert.call('Invalid YAML is a controlled failure') do
  parsed, errors = BlogPostDescriptions.parse_source("---\ndescription: [\n---\n", 'example.md')
  parsed.nil? && errors.any? { |row| row[:issue] == 'invalid-frontmatter' }
end
assert.call('Missing frontmatter fails closed') do
  parsed, errors = BlogPostDescriptions.parse_source('No metadata', 'example.md')
  parsed.nil? && errors.any? { |row| row[:issue] == 'missing-frontmatter' }
end
assert.call('A folded YAML scalar without a trailing newline is supported') do
  changed = source.sub("description: #{JSON.generate(description)}", "description: >-\n  #{description}")
  parsed, errors = BlogPostDescriptions.parse_source(changed, 'example.md')
  errors.empty? && parsed.data['description'] == description
end

git_variables, git_status = Open3.capture2('git', 'rev-parse', '--local-env-vars')
raise 'Cannot isolate Git fixture environment' unless git_status.success?

fixture_env = git_variables.lines.to_h { |name| [name.strip, nil] }
fixture_env.merge!('GIT_CONFIG_GLOBAL' => File::NULL, 'GIT_CONFIG_NOSYSTEM' => '1')
Dir.mktmpdir('post-descriptions-') do |root|
  checker = File.expand_path('../kkamji_scripts/blog/check_post_descriptions.rb', __dir__)
  FileUtils.mkdir_p(File.join(root, '_posts'))
  path = File.join(root, '_posts/example.md')
  File.write(path, source)
  _output, status = Open3.capture2(fixture_env, 'git', 'init', '--quiet', root)
  raise 'Cannot initialize isolated test repository' unless status.success?

  _output, status = Open3.capture2(fixture_env, 'git', 'add', '--', '_posts/example.md', chdir: root)
  raise 'Cannot stage isolated fixture' unless status.success?

  run = lambda do |*args|
    Open3.capture3(fixture_env, RbConfig.ruby, checker, '--root', root, *args)
  end
  assert.call('The CLI reads all tracked source posts') { run.call.last.success? }
  File.write(path, source.sub(/^description:.*\n/, ''))
  assert.call('The source CLI rejects a missing description') do
    stdout, stderr, status = run.call
    !status.success? && stdout.include?('1 posts, 1 findings') && stderr.include?('missing-or-invalid-description')
  end
  assert.call('The staged CLI uses index bytes, not unstaged metadata') { run.call('--staged').last.success? }
  _output, status = Open3.capture2(fixture_env, 'git', 'add', '--', '_posts/example.md', chdir: root)
  raise 'Cannot update isolated fixture index' unless status.success?

  File.write(path, source)
  assert.call('An unstaged fix cannot hide an invalid staged description') do
    _stdout, stderr, status = run.call('--staged')
    !status.success? && stderr.include?('missing-or-invalid-description')
  end
  File.unlink(path)
  assert.call('A sparse or missing tracked post is not silently skipped') do
    _stdout, stderr, status = run.call
    !status.success? && stderr.include?('missing-source-file')
  end
end

Dir.mktmpdir('post-description-rename-') do |root|
  FileUtils.mkdir_p(File.join(root, '_posts'))
  old_path = File.join(root, '_posts/2000-01-01-before.md')
  new_path = File.join(root, '_posts/2000-01-01-after.md')
  File.write(old_path, source + ("Repeated fixture paragraph.\n" * 100))
  git = lambda do |*args|
    stdout, stderr, status = Open3.capture3(fixture_env, 'git', *args, chdir: root)
    raise "Isolated Git fixture failed: #{stderr}" unless status.success?

    stdout
  end
  git.call('init', '--quiet')
  git.call('add', '--', '_posts')
  git.call('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.com', '-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'test: seed description fixture')
  File.rename(old_path, new_path)
  File.write(new_path, File.read(new_path).sub(/^description:.*\n/, ''))
  git.call('add', '-A', '--', '_posts')
  assert.call('The rename fixture is classified as a rename, not add/delete') do
    git.call('diff', '--cached', '--name-status').start_with?('R')
  end
  hook = File.read(File.expand_path('../.githooks/pre-commit', __dir__))
  selector = hook.lines.find { |line| line.start_with?('description_inputs=') }
  command = Shellwords.split(selector.match(/\Adescription_inputs="\$\((.+)\)"\s*\z/)[1])
  raise 'Unexpected staged-description selector' unless command[0, 2] == %w[git diff]

  selected, status = Open3.capture2(fixture_env, *command, chdir: root)
  assert.call('The actual pre-commit selector includes renamed posts') do
    status.success? && selected.include?('_posts/2000-01-01-after.md')
  end
  checker = File.expand_path('../kkamji_scripts/blog/check_post_descriptions.rb', __dir__)
  _, stderr, status = Open3.capture3(fixture_env, RbConfig.ruby, checker, '--root', root, '--staged')
  assert.call('A selected rename with a removed description fails the staged gate') do
    !selected.empty? && !status.success? && stderr.include?('missing-or-invalid-description')
  end
end

require 'jekyll'
require 'jekyll-seo-tag'
require_relative '../_plugins/post-descriptions'

Dir.mktmpdir('post-description-build-') do |root|
  FileUtils.mkdir_p(File.join(root, '_posts'))
  FileUtils.mkdir_p(File.join(root, '_layouts'))
  path = File.join(root, '_posts/2000-01-01-example.md')
  fixture_source = source.sub('2026-11-06 12:00:00 +0900', '2000-01-01 12:00:00 +0900')
  fixture_source = fixture_source.sub('title: Example', "layout: post\ntitle: Example")
  layout_path = File.join(root, '_layouts/post.html')
  layout = <<~HTML
    <!doctype html><html><head>
    <meta name="description" content="{{ page.description | escape }}">
    <meta property="og:description" name="twitter:description" content="{{ page.description | escape }}">
    <script type="application/ld+json">{"@type":"BlogPosting","description":{{ page.description | jsonify }}}</script>
    </head><body><p class="post-desc">{{ page.description | escape }}</p>{{ content }}</body></html>
  HTML
  File.write(layout_path, layout)
  File.write(path, fixture_source)
  fixture_defaults = []
  build = lambda do
    configuration = Jekyll.configuration(
      'source' => root, 'destination' => File.join(root, '_site'), 'quiet' => true,
      'plugins_dir' => [], 'plugins' => ['jekyll-seo-tag'], 'cache_dir' => File.join(root, '.cache'),
      'defaults' => fixture_defaults
    )
    Jekyll::Site.new(configuration).process
  end
  assert.call('Real Jekyll post_render sees the complete layout and its metadata') do
    build.call
    Dir.glob(File.join(root, '_site/**/*.html')).length == 1
  end
  File.write(path, fixture_source.sub(/^description:.*\n/, ''))
  assert.call('Real Jekyll build refuses missing source descriptions') do
    begin
      build.call
      false
    rescue Jekyll::Errors::FatalException => error
      error.message.include?('missing-or-invalid-description')
    end
  end
  File.write(path, fixture_source)
  File.write(layout_path, layout.sub('<p class="post-desc">{{ page.description | escape }}</p>', '<p class="post-desc">Generated excerpt</p>'))
  assert.call('Real Jekyll build refuses an obsolete rendered excerpt') do
    begin
      build.call
      false
    rescue Jekyll::Errors::FatalException => error
      error.message.include?('rendered-subtitle')
    end
  end
  quoted = "cert-manager와 ClusterIssuer로 Let's Encrypt의 ACME 발급을 설정하는 방법을 설명합니다. 설치부터 TLS 설정과 인증서 확인을 다룹니다."
  File.write(path, fixture_source.sub(JSON.generate(description), JSON.generate(quoted)))
  File.write(layout_path, '<!doctype html><html><head>{% seo %}</head><body><p class="post-desc">{{ page.description | escape }}</p>{{ content }}</body></html>')
  assert.call('Real SEO typography preserves the authored description without a false mismatch') do
    build.call
    rendered = File.read(Dir.glob(File.join(root, '_site/**/*.html')).first)
    metadata = Nokogiri::HTML(rendered).at_css('meta[name="description"]')['content']
    metadata.include?("Let\u2019s Encrypt")
  end
  Jekyll::Hooks.register :posts, :pre_render do |document|
    if document.data['test_description_override'] == 'in-place'
      document.data['description'].replace('원문과 다른 짧은 설명입니다.')
    elsif document.data['test_description_override']
      document.data['description'] = '원문과 다른 짧은 설명입니다.'
    end
  end
  File.write(path, fixture_source.sub('layout: post', "layout: post\ntest_description_override: true"))
  assert.call('A pre_render mutation cannot replace the source description') do
    begin
      build.call
      false
    rescue Jekyll::Errors::FatalException => error
      error.message.include?('description-changed-from-source')
    end
  end
  File.write(path, fixture_source.sub('layout: post', "layout: post\ntest_description_override: in-place"))
  assert.call('An in-place data mutation cannot modify the immutable source snapshot') do
    begin
      build.call
      false
    rescue Jekyll::Errors::FatalException => error
      error.message.include?('description-changed-from-source')
    end
  end
  File.write(path, fixture_source.sub(/^description:.*\n/, ''))
  fixture_defaults << { 'scope' => { 'path' => '', 'type' => 'posts' }, 'values' => { 'description' => description } }
  assert.call('Frontmatter defaults cannot hide a missing explicit source description') do
    begin
      build.call
      false
    rescue Jekyll::Errors::FatalException => error
      error.message.include?('missing-or-invalid-description')
    end
  end
  [
    ['emphasis-star', '*강조*', 'description-markup'],
    ['emphasis-underscore', '_강조_', 'description-markup'],
    ['reference-link', '[문서][참조]', 'description-markup'],
    ['fullwidth-comma', 0xff0c.chr(Encoding::UTF_8), 'description-punctuation'],
    ['bullet', 0x2022.chr(Encoding::UTF_8), 'description-punctuation'],
    ['line-separator', 0x2028.chr(Encoding::UTF_8), 'description-control-character'],
    ['paragraph-separator', 0x2029.chr(Encoding::UTF_8), 'description-control-character']
  ].each do |label, suffix, expected_issue|
    invalid = "#{description} #{suffix} 내용"
    scalar = JSON.generate(invalid).gsub("\u2028", '\u2028').gsub("\u2029", '\u2029')
    File.write(path, fixture_source.sub(JSON.generate(description), scalar))
    assert.call("Real SEO build rejects invalid authored metadata: #{label}") do
      begin
        build.call
        false
      rescue Jekyll::Errors::FatalException => error
        error.message.include?(expected_issue)
      end
    end
  end
end

failures.each { |label| warn "FAIL: #{label}" }
puts "#{checks} checks, #{failures.length} failures"
exit(failures.empty? ? 0 : 1)
