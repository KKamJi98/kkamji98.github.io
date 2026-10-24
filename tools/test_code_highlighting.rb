# frozen_string_literal: true

require 'rouge'
require 'kramdown'
require 'kramdown-parser-gfm'
require 'nokogiri'

plugin = File.expand_path('../_plugins/code-highlighting.rb', __dir__)
require plugin if File.file?(plugin)

failures = []
checks = 0
assert = lambda do |label, &test|
  checks += 1
  failures << label unless test.call
end

def tokens(language, source)
  lexer = Rouge::Lexer.find(language)
  lexer ? lexer.new.lex(source).to_a : []
end

def clean?(language, source)
  result = tokens(language, source)
  !result.empty? && result.none? { |token, _| token == Rouge::Token['Error'] } && result.map(&:last).join == source
end

hcl = <<~'HCL'
  locals {
    escaped = replace("a.b", "/([.^$|?*+()\\[\\]{}\\\\])/", "\\$1")
    escaped_quotes = "a\"b\n\r\t\u0041\U0001F600"
    enabled = true
    timeout = 300
  }
HCL
assert.call('HCL preserves valid escapes and closing braces') { clean?('hcl', hcl) }
assert.call('Terraform alias uses the corrected HCL boundaries') { clean?('terraform', hcl) }
assert.call('HCL keeps heredoc content verbatim') { clean?('hcl', "x = <<-EOT\n  ${var.name} { \\\n  EOT\n") }
assert.call('Hyphenated heredoc delimiters stop before following code') do
  source = "x = <<-EOT-END\nhello\nEOT-END\ny = 1\n"
  result = tokens('hcl', source)
  clean?('hcl', source) && result.any? { |token, value| token == Rouge::Token['Name.Other'] && value == 'y' }
end
assert.call('An invalid escape after a heredoc is not swallowed') do
  !clean?('hcl', "x = <<-EOT-END\nhello\nEOT-END\ny = \"\\q\"\n")
end
assert.call('HCL accepts standalone function expressions') { clean?('hcl', "templatefile(path, vars)\n") }
assert.call('HCL still reports invalid escapes') { !clean?('hcl', 'x = "\q"') }
assert.call('HCL nested arrays and objects keep their boundaries') do
  clean?('hcl', "x = [{ enabled = true }, { count = 2 }]\ny = { a = { b = false } }\n")
end
markdown = "같은 문단에서 줄을\\\n바꿉니다.\n"
assert.call('Markdown accepts a backslash hard line break') { clean?('markdown', markdown) }
solidity = <<~'SOL'
  // SPDX-License-Identifier: MIT
  pragma solidity ^0.8.24;
  contract Escrow {
      mapping(address => uint256) public balances;
      event Deposit(address indexed sender, uint256 value);
      function deposit() external payable { balances[msg.sender] += msg.value; }
  }
SOL
assert.call('Solidity is a registered lexer and preserves source') { clean?('solidity', solidity) }
assert.call('Solidity supports single-quoted strings') { clean?('solidity', "contract C { string s = 'hello'; }\n") }
assert.call('Solidity supports hex and Unicode string prefixes') do
  clean?('solidity', "contract C { bytes b = hex'0123'; string s = unicode\"안녕\"; }\n")
end
assert.call('Solidity supports dollar-sign identifiers') { clean?('solidity', 'contract C { uint $balance; }') }
assert.call('Solidity still rejects invalid string escapes') { !clean?('solidity', 'contract C { string s = "\q"; }') }
assert.call('Solidity marks its own keywords and numeric types') do
  result = tokens('solidity', solidity)
  result.any? { |token, value| token.qualname.start_with?('Keyword') && value == 'contract' } &&
    result.any? { |token, value| token == Rouge::Token['Keyword.Type'] && value == 'uint256' }
end
html = Kramdown::Document.new("```hcl\n#{hcl}```\n", input: 'GFM', syntax_highlighter: 'rouge').to_html
assert.call('Rendered HCL has no error spans and preserves copy text') do
  doc = Nokogiri::HTML.fragment(html)
  doc.css('span.err').empty? && doc.at_css('code').text == hcl
end
assert.call('Other lexers retain real error detection') { !clean?('json', "{\"x\": 1}, {\"y\": 2}\n") }

require_relative '../kkamji_scripts/blog/check_code_blocks'

assert.call('Source gate rejects an unknown fence language') do
  BlogCodeBlocks.inspect_source("```not-a-real-language\nx\n```\n", 'example.md')[:findings].any? { |row| row[:issue] == 'unknown-language' }
end
assert.call('Source gate rejects lexer errors without exposing source text') do
  result = BlogCodeBlocks.inspect_source("```json\n{\"x\": 1}, {\"y\": 2}\n```\n", 'example.md')
  result[:findings] == [{ path: 'example.md', line: 1, language: 'json', issue: 'lexer-error' }]
end
assert.call('Source gate reports frontmatter-aware line numbers') do
  result = BlogCodeBlocks.inspect_source("---\ntitle: Example\n---\n\n```bad-language\nx\n```\n", 'example.md')
  result[:findings].first[:line] == 5
end
assert.call('Nested fence examples do not become additional code blocks') do
  result = BlogCodeBlocks.inspect_source("````markdown\n```hcl\nx = 1\n```\n````\n", 'example.md')
  result[:blocks] == 1 && result[:findings].empty?
end
assert.call('Unclosed fences cannot silently render as prose') do
  BlogCodeBlocks.inspect_source("```ruby\nx = 1\n", 'example.md')[:findings].any? { |row| row[:issue] == 'unclosed-fence' }
end
assert.call('A second language fence cannot silently merge code blocks') do
  source = "```shell\nterraform state show example\n```hcl\nx = 1\n```\n"
  BlogCodeBlocks.inspect_source(source, 'example.md')[:findings].any? { |row| row[:issue] == 'nested-fence-with-language' }
end
assert.call('Tilde fences and longer nested fences close correctly') do
  BlogCodeBlocks.inspect_source("~~~~markdown\n~~~ruby\nx = 1\n~~~\n~~~~\n", 'example.md')[:findings].empty?
end
assert.call('Rendered gate catches nested error tokens') do
  BlogCodeBlocks.inspect_html('<div class="language-hcl highlighter-rouge"><pre><span class="err">x</span></pre></div>', 'example.html')[:findings].any? { |row| row[:issue] == 'rendered-lexer-error' }
end
assert.call('Rendered gate catches unsupported languages') do
  BlogCodeBlocks.inspect_html('<div class="language-bad-language highlighter-rouge"><pre>x</pre></div>', 'example.html')[:findings].any? { |row| row[:issue] == 'rendered-unknown-language' }
end
assert.call('Rendered gate does not interpret escaped HTML as an error token') do
  BlogCodeBlocks.inspect_html('<div class="language-text highlighter-rouge"><pre>&lt;span class="err"&gt;x&lt;/span&gt;</pre></div>', 'example.html')[:findings].empty?
end

failures.each { |label| warn "FAIL: #{label}" }
puts "#{checks - failures.length}/#{checks} highlighting checks passed"
exit(failures.empty? ? 0 : 1)
