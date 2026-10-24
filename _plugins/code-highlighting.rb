# frozen_string_literal: true

require 'rouge'

module Rouge
  module Lexers
    class Hcl
      prepend :dq do
        rule %r/\\(?:[nrt"\\]|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8})/, Str::Escape
      end

      state :root do
        mixin :comments_and_whitespace
        rule %r/(<<-?)([ \t]*)([a-zA-Z_][a-zA-Z0-9_-]*)/ do |match|
          groups Operator, Text, Name::Constant
          @heredocstr = match[3]
          push :heredoc
        end
        mixin :primitives
        rule %r/[{}\[\](),.]/, Punctuation
        rule %r/[$a-z_\-][a-z0-9_\-]*/i do |match|
          value = match[0]
          if self.class.constants.include?(value)
            token Keyword::Constant
          elsif self.class.keywords.include?(value)
            token Keyword
          elsif self.class.declarations.include?(value)
            token Keyword::Declaration
          else
            token Name::Other
          end
        end
      end

      state :heredoc_nl do
        rule %r/[ \t]*([a-zA-Z_][a-zA-Z0-9_-]*)[ \t]*(?:\r?\n|\z)/ do |match|
          if match[1] == @heredocstr
            token Name::Constant
            pop! 2
          else
            token Str::Heredoc
          end
        end
        rule(//) { pop! }
      end
    end

    class Terraform
      prepend :dq do
        rule %r/\$+(?![${])/, Str::Double
      end
    end

    class Markdown
      prepend :root do
        rule %r/\\\n/, Str::Escape
      end
    end

    class Solidity < RegexLexer
      title 'Solidity'
      desc 'Solidity contract syntax'
      tag 'solidity'
      aliases 'sol'
      filenames '*.sol'

      def self.keywords
        @keywords ||= Set.new(%w[
          abstract anonymous assembly break calldata constant constructor continue
          contract delete do else emit enum error event external fallback for function
          if immutable import indexed interface internal is library memory modifier
          new override payable pragma private public pure receive return returns
          revert storage struct throw try type unchecked using view virtual while
        ])
      end

      def self.keywords_type
        @keywords_type ||= Set.new(%w[address bool string bytes fixed ufixed]) +
          Set.new((8..256).step(8).flat_map { |bits| ["uint#{bits}", "int#{bits}"] }) +
          Set.new((1..32).map { |bytes| "bytes#{bytes}" }) + Set.new(%w[uint int])
      end

      state :root do
        rule %r/\s+/, Text
        rule %r{//[^\n]*}, Comment::Single
        rule %r{/\*.*?(?:\*/|\z)}m, Comment::Multiline
        rule %r/\b(?:hex|unicode)(?=["'])/, Str::Affix
        rule %r/"/, Str::Double, :double_string
        rule %r/'/, Str::Single, :single_string
        rule %r/0[xX][0-9a-fA-F_]+/, Num::Hex
        rule %r/(?:[0-9][0-9_]*\.[0-9_]*|\.[0-9][0-9_]*)(?:[eE][+-]?[0-9_]+)?/, Num::Float
        rule %r/[0-9][0-9_]*(?:[eE][+-]?[0-9_]+)?/, Num::Integer
        rule %r/[$a-zA-Z_][$a-zA-Z_0-9]*/ do |match|
          value = match[0]
          if self.class.keywords_type.include?(value)
            token Keyword::Type
          elsif self.class.keywords.include?(value)
            token Keyword
          elsif %w[true false].include?(value)
            token Keyword::Constant
          else
            token Name
          end
        end
        rule %r/[{}\[\]();,.]/, Punctuation
        rule %r/[-+*\/%=!<>|&^~?:]/, Operator
      end

      state :string_escape do
        rule %r/\\(?:["'\\nrt]|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|\r?\n)/, Str::Escape
      end

      state :double_string do
        mixin :string_escape
        rule %r/[^"\\\r\n]+/, Str::Double
        rule %r/"/, Str::Double, :pop!
      end

      state :single_string do
        mixin :string_escape
        rule %r/[^'\\\r\n]+/, Str::Single
        rule %r/'/, Str::Single, :pop!
      end
    end
  end
end
