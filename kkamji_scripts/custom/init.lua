-- ~/.config/nvim/init.lua
-- 풀버전: 성능/UX/안정성/충돌 최소화

--------------------------------
-- 기본 옵션
--------------------------------
vim.g.mapleader = " "
vim.g.markdown_recommended_style = 0

vim.opt.number = true
vim.opt.autoindent = true
vim.opt.tabstop = 2
vim.opt.expandtab = true
vim.opt.shiftwidth = 2
vim.opt.smarttab = true
vim.opt.softtabstop = 2
vim.opt.termguicolors = true
vim.opt.mouse = "" -- 터미널 복사 충돌 방지
vim.opt.ignorecase = true
vim.opt.smartcase = true

-- UX 강화
vim.opt.clipboard     = "unnamedplus"
vim.opt.cursorline    = true
vim.opt.signcolumn    = "yes"
vim.opt.scrolloff     = 5
vim.opt.sidescrolloff = 8
vim.opt.splitbelow    = true
vim.opt.splitright    = true
vim.opt.updatetime    = 200
vim.opt.timeoutlen    = 400
vim.opt.undofile      = true
vim.opt.inccommand    = "split"
vim.opt.list          = true
vim.opt.listchars     = { tab = "▸ ", trail = "•", extends = ">", precedes = "<" }
vim.opt.fillchars     = { eob = " ", fold = " ", foldopen = "▾", foldclose = "▸" }
vim.opt.shortmess:append("I") -- intro 숨김
vim.opt.wrap = true
vim.opt.linebreak = true
vim.opt.breakindent = true

-- Python3 provider (UltiSnips/cmp 대비)
if vim.fn.executable("python3") == 1 then
  vim.g.python3_host_prog = vim.fn.exepath("python3")
end
vim.g.loaded_perl_provider = 0
vim.g.loaded_ruby_provider = 0

-- Python3 host 헬스체크 (pynvim 모듈 유무 확인)
local function has_python3_host()
  if vim.g.__python3_host_ok ~= nil then
    return vim.g.__python3_host_ok == 1
  end
  if vim.fn.executable("python3") ~= 1 then
    vim.g.__python3_host_ok = 0
    return false
  end
  local prog = vim.g.python3_host_prog or vim.fn.exepath("python3")
  local cmd = { prog, "-c", "import importlib,sys; sys.exit(0) if importlib.util.find_spec('pynvim') else sys.exit(1)" }
  vim.fn.system(cmd)
  local ok = (vim.v.shell_error == 0)
  vim.g.__python3_host_ok = ok and 1 or 0
  return ok
end

-- Git/cURL 트레이스 차단(부팅 시 불필요 로그 방지)
vim.env.GIT_TRACE = nil
vim.env.GIT_TRACE_CURL = nil
vim.env.GIT_CURL_VERBOSE = nil

local local_bin = vim.fs.normalize("~/.local/bin")
if vim.fn.isdirectory(local_bin) == 1 then
  if not vim.env.PATH:find(local_bin, 1, true) then
    vim.env.PATH = local_bin .. ":" .. vim.env.PATH
  end
end

-- UltiSnips: snipMate 디렉토리 충돌 방지. 반드시 플러그인 로딩 전에 설정
vim.g.UltiSnipsSnippetDirectories = { "UltiSnips" }

--------------------------------
-- 공용 LSP 헬퍼
--------------------------------
local function lsp_capabilities()
  local caps = vim.lsp.protocol.make_client_capabilities()
  caps.textDocument.foldingRange = {
    dynamicRegistration = false,
    lineFoldingOnly = true,
  }
  local ok, cmp_nvim_lsp = pcall(require, "cmp_nvim_lsp")
  if ok then caps = cmp_nvim_lsp.default_capabilities(caps) end
  return caps
end

local function lsp_on_attach(_, bufnr)
  vim.api.nvim_buf_set_option(bufnr, "omnifunc", "v:lua.vim.lsp.omnifunc")
  local buf = function(mode, lhs, rhs, desc)
    vim.keymap.set(mode, lhs, rhs, { noremap = true, silent = true, buffer = bufnr, desc = desc })
  end
  buf("n", "gd", vim.lsp.buf.definition,        "Go to definition")
  buf("n", "gr", vim.lsp.buf.references,        "References")
  buf("n", "gi", vim.lsp.buf.implementation,    "Implementation")
  buf("n", "K",  vim.lsp.buf.hover,             "Hover")
  buf("n", "gs", vim.lsp.buf.signature_help,    "Signature help")
  buf("n", "<leader>rn", vim.lsp.buf.rename,    "Rename symbol")
  buf("n", "<leader>ca", vim.lsp.buf.code_action,"Code action")
  buf("n", "gl", vim.diagnostic.open_float,     "Line diagnostics")
  buf("n", "[d", vim.diagnostic.goto_prev,      "Prev diagnostic")
  buf("n", "]d", vim.diagnostic.goto_next,      "Next diagnostic")
  if vim.lsp.buf.format then
    buf("n", "<leader>cf", function() vim.lsp.buf.format({ async = true }) end, "Format buffer")
  end
end

local function configure_lsp(server, opts)
  local base = {
    on_attach = lsp_on_attach,
    capabilities = lsp_capabilities(),
  }
  vim.lsp.config(server, vim.tbl_deep_extend("force", {}, base, opts or {}))
end

local function enable_lsp(server)
  local ok, err = pcall(vim.lsp.enable, server)
  if not ok then
    vim.schedule(function()
      vim.notify(("LSP enable failed for %s: %s"):format(server, err), vim.log.levels.WARN, { title = "LSP" })
    end)
  end
end

--------------------------------
-- lazy.nvim 부트스트랩
--------------------------------
local uv = vim.uv or vim.loop
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (uv.fs_stat and uv.fs_stat(lazypath)) then
  if vim.fn.executable("git") == 1 then
    local cmd = {
      "git","-c","http.extraHeader=","-c","http.proxy=","-c","https.proxy=",
      "clone","--filter=blob:none","https://github.com/folke/lazy.nvim.git","--branch=stable",lazypath,
    }
    if vim.system then
      vim.system(cmd, { stdout = false, stderr = false }):wait()
    else
      vim.fn.system({ "sh","-c", table.concat(cmd, " ") .. " >/dev/null 2>&1" })
    end
  end
end
vim.opt.rtp:prepend(lazypath)

--------------------------------
-- 플러그인
--------------------------------
require("lazy").setup({
  -- Lua LS에 Neovim API 타입 주입
  { "folke/neodev.nvim", lazy = false, opts = {}, priority = 10000 },

  -- 테마
  {
    "folke/tokyonight.nvim",
    priority = 9999,
    lazy = false,
    config = function()
      ---@diagnostic disable-next-line: missing-fields
      require("tokyonight").setup({
        style = "storm",
        on_highlights = function(hl, _)
          hl.LineNr = { fg = "#00ff00" }
          hl.CursorLineNr = { fg = "#ff66ff", bold = true }
        end,
      })
      vim.cmd("colorscheme tokyonight")
    end,
  },

  -- 아이콘
  { "nvim-tree/nvim-web-devicons", lazy = true, opts = { default = true } },
  { "echasnovski/mini.icons", lazy = true, version = false, opts = {} },
  {
    "ojroques/nvim-osc52",
    event = "VeryLazy",
    config = function()
      local osc52 = require("osc52")
      osc52.setup({ silent = true })
      local function paste()
        return { vim.fn.getreg("+", 1, true), vim.fn.getregtype("+") }
      end
      vim.g.clipboard = {
        name = "osc52",
        copy = {
          ["+"] = function(lines)
            osc52.copy(table.concat(lines, "\n"))
          end,
          ["*"] = function(lines)
            osc52.copy(table.concat(lines, "\n"))
          end,
        },
        paste = {
          ["+"] = paste,
          ["*"] = paste,
        },
      }
    end,
  },

  -- 상태줄
  {
    "nvim-lualine/lualine.nvim",
    event = "VeryLazy",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
      require("lualine").setup({ options = { theme = "tokyonight", icons_enabled = true } })
    end,
  },

  -- 파일 트리
  {
    "nvim-tree/nvim-tree.lua",
    cmd = { "NvimTreeToggle", "NvimTreeFindFile", "NvimTreeRefresh", "NvimTreeFocus" },
    keys = {
      { "<C-n>",     "<cmd>NvimTreeToggle<CR>",    mode = "n", silent = true, desc = "NvimTree Toggle" },
      { "<leader>fe","<cmd>NvimTreeFindFile<CR>",  mode = "n", silent = true, desc = "NvimTree Find Current File" },
      { "<leader>ne","<cmd>NvimTreeFocus<CR>",     mode = "n", silent = true, desc = "NvimTree Focus" },
      { "<leader>fr","<cmd>NvimTreeRefresh<CR>",   mode = "n", silent = true, desc = "NvimTree Refresh" },
      { "<leader>er", function() local api=require("nvim-tree.api"); api.tree.focus(); api.fs.rename() end,
        mode="n", silent=true, desc="Explorer: Rename" },
      { "<leader>en", function() local api=require("nvim-tree.api"); api.tree.focus(); api.fs.create() end,
        mode="n", silent=true, desc="Explorer: New (file/dir)" },
      { "<leader>ed", function() local api=require("nvim-tree.api"); api.tree.focus(); api.fs.remove() end,
        mode="n", silent=true, desc="Explorer: Delete" },
      { "<leader>em", function() local api=require("nvim-tree.api"); api.tree.focus(); api.fs.rename_sub() end,
        mode="n", silent=true, desc="Explorer: Move/Rename (path)" },
      { "<leader>et", function()
          local api = require("nvim-tree.api")
          local in_tree = false
          if api.tree.is_tree_buf then
            in_tree = api.tree.is_tree_buf(0)
          else
            in_tree = (vim.bo.filetype == "NvimTree")
          end

          if in_tree then
            vim.cmd("wincmd p")
            local still_tree = (api.tree.is_tree_buf and api.tree.is_tree_buf(0)) or (vim.bo.filetype == "NvimTree")
            if still_tree then
              for _, win in ipairs(vim.api.nvim_list_wins()) do
                local buf = vim.api.nvim_win_get_buf(win)
                if vim.bo[buf].filetype ~= "NvimTree" then
                  vim.api.nvim_set_current_win(win)
                  break
                end
              end
            end
          else
            if api.tree.is_visible and api.tree.is_visible() then
              api.tree.focus()
            else
              api.tree.open()
            end
          end
        end,
        mode="n", silent=true, desc="Explorer: Focus Toggle" },
    },
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
      require("nvim-tree").setup({
        view = { width = 36 },
        renderer = { group_empty = true },
        filters = { dotfiles = false },
        git = { enable = true },
      })
    end,
  },

  -- 키맵 가이드
  {
    "folke/which-key.nvim",
    event = "VeryLazy",
    config = function()
      local wk = require("which-key")
      wk.setup({
        win = {
          border = "rounded",
          title = true,
          title_pos = "center",
        },
      })
      wk.add({
        { "<leader>f", group = "find" },
        { "<leader>e", group = "explorer" },
        { "<leader>c", group = "code" },
        { "<leader>s", group = "session" },
        { "<leader>x", group = "diagnostics" },
        { "<leader>m", group = "markdown" },
        { "<leader>mt", desc = "Toggle checkbox" },
        { "<leader>mr", desc = "Renumber ordered list" },
        { "<leader>ms", desc = "Toggle spell checking" },
      })
    end,
  },

  -- 주석: Ctrl+/
  {
    "numToStr/Comment.nvim",
    event = { "BufReadPost", "BufNewFile" },
    config = function()
      local api = require("Comment.api")
      require("Comment").setup()
      vim.keymap.set("n", "<C-_>", function() api.toggle.linewise.current() end, { noremap = true, silent = true, desc="Toggle Comment" })
      vim.keymap.set("x", "<C-_>", function() api.toggle.linewise(vim.fn.visualmode()) end, { noremap = true, silent = true, desc="Toggle Comment (v)" })
    end,
  },

  -- Treesitter
  {
    "nvim-treesitter/nvim-treesitter",
    build = ":TSUpdate",
    event = { "BufReadPost", "BufNewFile" },
    dependencies = {
      "nvim-treesitter/nvim-treesitter-textobjects",
    },
    config = function()
      require("nvim-treesitter.configs").setup({
        ensure_installed = { "lua", "terraform", "hcl", "yaml", "json", "bash", "markdown", "markdown_inline", "go", "python" },
        highlight = { enable = true },
        indent = { enable = true, disable = { "yaml", "markdown" } }, -- YAML/Markdown 인덴트 비활성화
        incremental_selection = {
          enable = true,
          keymaps = {
            init_selection = "gnn",
            node_incremental = "grn",
            scope_incremental = "grc",
            node_decremental = "grm",
          },
        },
        textobjects = {
          select = {
            enable = true,
            lookahead = true,
            keymaps = {
              ["af"] = "@function.outer",
              ["if"] = "@function.inner",
              ["ac"] = "@class.outer",
              ["ic"] = "@class.inner",
            },
          },
          move = {
            enable = true,
            set_jumps = true,
            goto_next_start = {
              ["]m"] = "@function.outer",
              ["]]"] = "@class.outer",
            },
            goto_previous_start = {
              ["[m"] = "@function.outer",
              ["[["] = "@class.outer",
            },
            goto_next_end = { ["]M"] = "@function.outer" },
            goto_previous_end = { ["[M"] = "@function.outer" },
          },
        },
        auto_install = false,
      })
    end,
  },

  -- Terraform
  {
    "hashivim/vim-terraform",
    ft = { "terraform", "tf", "hcl" },
    config = function()
      vim.g.terraform_fmt_on_save = 1
      vim.g.terraform_align = 1
    end,
  },

  -- Mason
  { "mason-org/mason.nvim", build = ":MasonUpdate", opts = {} },

  -- Mason LSP bridge
  {
    "mason-org/mason-lspconfig.nvim",
    dependencies = { "mason-org/mason.nvim", "neovim/nvim-lspconfig" },
    opts = {
      ensure_installed = { "terraformls", "lua_ls", "yamlls" },
      automatic_enable = { exclude = { "terraformls" } },
    },
  },

  -- LSP 설정 (terraformls는 하단 TFENV 블록에서 구성)
  {
    "neovim/nvim-lspconfig",
    event = { "BufReadPre", "BufNewFile" },
    dependencies = { "folke/neodev.nvim", "b0o/schemastore.nvim" },
    config = function()
      vim.diagnostic.config({
        virtual_text = { spacing = 2, prefix = "●" },
        float = { border = "rounded" },
        severity_sort = true,
      })

      require("neodev").setup({})

      -- Lua
      configure_lsp("lua_ls", {
        settings = {
          Lua = {
            runtime = { version = "LuaJIT" },
            diagnostics = { globals = { "vim" } },
            workspace = { checkThirdParty = false, library = vim.api.nvim_get_runtime_file("", true) },
            telemetry = { enable = false },
          },
        },
      })

      -- YAML (SchemaStore)
      local ok_schema, schemastore = pcall(require, "schemastore")
      local yaml_schemas = {}
      if ok_schema then
        yaml_schemas = schemastore.yaml.schemas()
      end
      configure_lsp("yamlls", {
        settings = {
          yaml = {
            validate = true,
            format = { enable = true },
            schemaStore = { enable = false },
            schemas = yaml_schemas,
            keyOrdering = false,
          },
        },
      })
    end,
  },

  -- Helm 템플릿 파일타입/하이라이트
  { "towolf/vim-helm", ft = { "helm" } },

  -- TFLint + yamllint
  {
    "mfussenegger/nvim-lint",
    ft = { "terraform", "tf", "hcl", "yaml" },
    config = function()
      local lint = require("lint")
      lint.linters_by_ft = {
        terraform = { "tflint" }, tf = { "tflint" }, hcl = { "tflint" },
        yaml = { "yamllint" },
      }
      vim.api.nvim_create_autocmd("BufWritePost", {
        callback = function() require("lint").try_lint() end,
      })
    end,
  },

  -- 스니펫: UltiSnips 먼저 로드 (Python host 있을 때만)
  { "SirVer/ultisnips", event = "InsertEnter", cond = has_python3_host },
  { "honza/vim-snippets", event = "InsertEnter" },

  -- 자동 완성 (cmp + UltiSnips)
  {
    "hrsh7th/nvim-cmp",
    event = "InsertEnter",
    dependencies = {
      { "quangnguyen30192/cmp-nvim-ultisnips", cond = has_python3_host, dependencies = { "SirVer/ultisnips" } },
      "hrsh7th/cmp-buffer",
      "hrsh7th/cmp-path",
      "hrsh7th/cmp-nvim-lsp",
    },
    config = function()
      local has_py = (vim.fn.has("python3") == 1) and (vim.fn.executable("python3") == 1)
      local has_ultisnips = (vim.fn.exists("*UltiSnips#Anon") == 1)

      local cmp = require("cmp")
      cmp.setup({
        snippet = {
          expand = function(args)
            if has_ultisnips then
              vim.fn["UltiSnips#Anon"](args.body)
            elseif vim.snippet and vim.snippet.expand then
              vim.snippet.expand(args.body)
            end
          end,
        },
        mapping = cmp.mapping.preset.insert({
          ["<C-n>"] = cmp.mapping.select_next_item({ behavior = cmp.SelectBehavior.Insert }),
          ["<C-p>"] = cmp.mapping.select_prev_item({ behavior = cmp.SelectBehavior.Insert }),
          ["<CR>"]  = cmp.mapping.confirm({ select = false }),
          ["<Tab>"] = cmp.mapping(function(fallback)
            if cmp.visible() then
              cmp.select_next_item()
            elseif has_ultisnips and vim.fn["UltiSnips#CanJumpForwards"]() == 1 then
              vim.api.nvim_feedkeys(
                vim.api.nvim_replace_termcodes("<Plug>(ultisnips_jump_forward)", true, true, true),
                "m",
                true
              )
            else
              fallback()
            end
          end, { "i", "s" }),
          ["<S-Tab>"] = cmp.mapping(function(fallback)
            if cmp.visible() then
              cmp.select_prev_item()
            elseif has_ultisnips and vim.fn["UltiSnips#CanJumpBackwards"]() == 1 then
              vim.api.nvim_feedkeys(
                vim.api.nvim_replace_termcodes("<Plug>(ultisnips_jump_backward)", true, true, true),
                "m",
                true
              )
            else
              fallback()
            end
          end, { "i", "s" }),
        }),
        sources = (function()
          local s = {
            { name = "nvim_lsp" },
            { name = "buffer" },
            { name = "path" },
          }
          if has_py and has_ultisnips then
            table.insert(s, 1, { name = "ultisnips" })
          end
          return s
        end)(),
        experimental = { ghost_text = false },
      })
    end,
  },

  -- 자동 괄호 (cmp confirm 연동)
  {
    "windwp/nvim-autopairs",
    event = "InsertEnter",
    config = function()
      local autopairs = require("nvim-autopairs")
      autopairs.setup({
        check_ts = true,
        fast_wrap = {},
        disable_filetype = { "TelescopePrompt", "vim" },
      })
      local ok, cmp = pcall(require, "cmp")
      if ok then
        local cmp_autopairs = require("nvim-autopairs.completion.cmp")
        cmp.event:on("confirm_done", cmp_autopairs.on_confirm_done())
      end
      autopairs.add_rules(require("nvim-autopairs.rules.endwise-lua"))
    end,
  },

  -- Telescope
  {
    "nvim-telescope/telescope.nvim",
    branch = "0.1.x",
    dependencies = { "nvim-lua/plenary.nvim" },
    cmd = "Telescope",
    keys = {
      { "<leader>ff", "<cmd>Telescope find_files<CR>", mode="n", silent=true, desc="Find files" },
      { "<leader>fg", "<cmd>Telescope live_grep<CR>",  mode="n", silent=true, desc="Live grep" },
      { "<leader>fb", "<cmd>Telescope buffers<CR>",    mode="n", silent=true, desc="Buffers" },
      { "<leader>fh", "<cmd>Telescope help_tags<CR>",  mode="n", silent=true, desc="Help tags" },
    },
    config = function()
      require("telescope").setup({
        defaults = {
          layout_strategy = "horizontal",
          sorting_strategy = "ascending",
          layout_config = { prompt_position = "top" },
        },
      })
    end,
  },
  {
    "nvim-telescope/telescope-file-browser.nvim",
    dependencies = { "nvim-telescope/telescope.nvim" },
    keys = {
      { "<leader>fB", function()
          require("telescope").extensions.file_browser.file_browser({
            path = "%:p:h", select_buffer = true, respect_gitignore = false, hidden = true,
          })
        end, mode="n", silent=true, desc="File Browser (buffer dir)" },
    },
    config = function()
      require("telescope").load_extension("file_browser")
    end,
  },

  -- Git 변경 표시
  {
    "lewis6991/gitsigns.nvim",
    event = { "BufReadPost", "BufNewFile" },
    config = function()
      require("gitsigns").setup({
        current_line_blame = false,
        current_line_blame_opts = { delay = 500 },
      })
      local gs = package.loaded.gitsigns
      vim.keymap.set("n", "]h", gs.next_hunk, { silent = true, desc = "Next hunk" })
      vim.keymap.set("n", "[h", gs.prev_hunk, { silent = true, desc = "Prev hunk" })
      vim.keymap.set("n", "<leader>hp", gs.preview_hunk, { silent = true, desc = "Preview hunk" })
      vim.keymap.set("n", "<leader>hs", gs.stage_hunk,   { silent = true, desc = "Stage hunk" })
      vim.keymap.set("n", "<leader>hu", gs.undo_stage_hunk, { silent = true, desc = "Undo stage hunk" })
    end,
  },

  -- 진단 패널
  {
    "folke/trouble.nvim",
    cmd = { "Trouble", "TroubleToggle" },
    dependencies = { "nvim-tree/nvim-web-devicons" },
    keys = {
      { "<leader>xx", "<cmd>Trouble diagnostics toggle<CR>", mode="n", silent=true, desc="Diagnostics" },
      { "<leader>xq", "<cmd>Trouble qflist toggle<CR>",      mode="n", silent=true, desc="Quickfix" },
    },
    opts = {},
  },

  -- 세션 복원
  {
    "folke/persistence.nvim",
    event = "BufReadPre",
    config = true,
    keys = {
      { "<leader>ss", function() require("persistence").load() end,                mode="n", silent=true, desc="Session restore" },
      { "<leader>sl", function() require("persistence").load({ last = true }) end, mode="n", silent=true, desc="Session last" },
      { "<leader>sd", function() require("persistence").stop() end,                mode="n", silent=true, desc="Session stop" },
    },
  },
}, {
  checker = { enabled = false },
  change_detection = { enabled = false },
  rocks = { enabled = false },
})

--------------------------------
-- 자동명령
--------------------------------
-- Yank 하이라이트
vim.api.nvim_create_autocmd("TextYankPost", {
  callback = function()
    vim.highlight.on_yank()
    if vim.v.event.operator == "y" then
      local reg = vim.v.event.regname
      if reg == "" or reg == "+" or reg == "*" then
        local ok, osc52 = pcall(require, "osc52")
        if ok then
          osc52.copy_register(reg == "" and "+" or reg)
        end
      end
    end
  end,
})

-- 외부 변경 자동 반영
vim.api.nvim_create_autocmd({ "FocusGained", "BufEnter", "CursorHold" }, {
  callback = function() if vim.fn.getcmdwintype() == "" then vim.cmd("checktime") end end,
})

-- 마지막 커서 위치 복귀
vim.api.nvim_create_autocmd("BufReadPost", {
  callback = function()
    local mark = vim.api.nvim_buf_get_mark(0, '"')
    local lcount = vim.api.nvim_buf_line_count(0)
    if mark[1] > 0 and mark[1] <= lcount then pcall(vim.api.nvim_win_set_cursor, 0, mark) end
  end,
})

-- 저장 시 트레일링 공백 제거(마크다운/커밋/Helm/Make 제외)
vim.api.nvim_create_autocmd("BufWritePre", {
  pattern = "*",
  callback = function()
    if not vim.bo.modifiable or vim.bo.readonly then
      return
    end
    local ft = vim.bo.filetype
    if ft ~= "markdown" and ft ~= "gitcommit" and ft ~= "helm" and ft ~= "make" then
      local view = vim.fn.winsaveview()
      vim.cmd([[%s/\s\+$//e]])
      vim.fn.winrestview(view)
    end
  end,
})

-- 시작 직후 메시지라인 정리
vim.schedule(function() vim.cmd("echo ''") vim.cmd("redraw!") end)

--------------------------------
-- 전역 키매핑
--------------------------------
local map = vim.keymap.set
local opts = { noremap = true, silent = true }
local function mapd(mode, lhs, rhs, desc)
  local o = desc and vim.tbl_extend("force", opts, { desc = desc }) or opts
  map(mode, lhs, rhs, o)
end

-- 창 이동
mapd("n", "<C-h>", "<C-w>h", "Window left")
mapd("n", "<C-j>", "<C-w>j", "Window down")
mapd("n", "<C-k>", "<C-w>k", "Window up")
mapd("n", "<C-l>", "<C-w>l", "Window right")

-- 편의
mapd("n", "<leader>w", "<cmd>write<CR>", "Write buffer")
mapd("n", "<leader>q", "<cmd>quit<CR>",  "Quit window")
mapd("n", "<leader>Q", "<cmd>qa!<CR>",   "Quit all (force)")
mapd("n", "<leader>h", "<cmd>nohlsearch<CR>", "Clear highlight")

-- UI 토글
mapd("n", "<leader>un", function() vim.wo.relativenumber = not vim.wo.relativenumber end, "Toggle relative number")

-- 창 크기 조절
mapd("n", "<C-Up>",    "<cmd>resize +2<CR>", "Increase height")
mapd("n", "<C-Down>",  "<cmd>resize -2<CR>", "Decrease height")
mapd("n", "<C-Left>",  "<cmd>vertical resize -3<CR>", "Decrease width")
mapd("n", "<C-Right>", "<cmd>vertical resize +3<CR>", "Increase width")

-- 라인/블록 이동
mapd("n", "<A-j>", ":m .+1<CR>==", "Move line down")
mapd("n", "<A-k>", ":m .-1<CR>==", "Move line up")
mapd("i", "<A-j>", "<Esc>:m .+1<CR>==gi", "Move line down")
mapd("i", "<A-k>", "<Esc>:m .-1<CR>==gi", "Move line up")
mapd("v", "<A-j>", ":m '>+1<CR>gv=gv", "Move block down")
mapd("v", "<A-k>", ":m '<-2<CR>gv=gv", "Move block up")

--------------------------------
-- 파일타입별 들여쓰기 규칙
--------------------------------
-- per-filetype indentation helper
local function set_local_indent(width, expandtab)
  local o = vim.opt_local
  o.tabstop = width
  o.shiftwidth = width
  o.softtabstop = width
  o.expandtab = expandtab
end

vim.api.nvim_create_autocmd("FileType", {
  pattern = { "python" },
  callback = function()
    set_local_indent(4, true)
  end,
})

vim.api.nvim_create_autocmd("FileType", {
  pattern = { "yaml", "yml", "docker-compose", "helm" },
  callback = function()
    set_local_indent(2, true)
  end,
})

--------------------------------
-- Markdown 편집 고도화
--------------------------------
local markdown = {} -- markdown-specific helpers

function markdown.toggle_checkbox_line(bufnr, line_nr)
  if line_nr < 0 then
    return false
  end
  local line = vim.api.nvim_buf_get_lines(bufnr, line_nr, line_nr + 1, false)[1]
  if not line then
    return false
  end
  local prefix, state, rest = line:match("^(%s*[%-%*+]%s+)%[([ xX%-])%]%s*(.*)$")
  if not prefix then
    prefix, state, rest = line:match("^(%s*%d+%.%s+)%[([ xX%-])%]%s*(.*)$")
  end
  if not prefix or not state then
    return false
  end
  local new_state = (state == " " or state == "-") and "x" or " "
  local suffix = rest ~= "" and (" " .. rest) or ""
  vim.api.nvim_buf_set_lines(bufnr, line_nr, line_nr + 1, false, { ("%s[%s]%s"):format(prefix, new_state, suffix) })
  return true
end

function markdown.toggle_checkbox_current()
  local bufnr = vim.api.nvim_get_current_buf()
  local row = vim.api.nvim_win_get_cursor(0)[1] - 1
  markdown.toggle_checkbox_line(bufnr, row)
end

function markdown.toggle_checkbox_visual()
  local bufnr = vim.api.nvim_get_current_buf()
  local start_line = vim.fn.getpos("'<")[2] - 1
  local end_line = vim.fn.getpos("'>")[2] - 1
  if start_line < 0 or end_line < 0 then
    return
  end
  if end_line < start_line then
    start_line, end_line = end_line, start_line
  end
  for line_nr = start_line, end_line do
    markdown.toggle_checkbox_line(bufnr, line_nr)
  end
end

function markdown.continue_list_newline()
  local line = vim.api.nvim_get_current_line()
  local indent, marker, rest = line:match("^(%s*)([%-%*+])%s+(.*)$")
  if marker then
    local checkbox, tail = rest:match("^%[([ xX%-])%]%s*(.*)$")
    local content = checkbox and tail or rest
    if content == "" then
      return "\n" .. indent
    end
    local continuation = indent .. marker .. " "
    if checkbox then continuation = continuation .. "[ ] " end
    return "\n" .. continuation
  end

  local number_indent, number, number_rest = line:match("^(%s*)(%d+)%.%s+(.*)$")
  if number then
    local checkbox, tail = number_rest:match("^%[([ xX%-])%]%s*(.*)$")
    local content = checkbox and tail or number_rest
    if content == "" then
      return "\n" .. number_indent
    end
    local next_number = tonumber(number)
    local continuation = number_indent .. (next_number and ("%d. "):format(next_number + 1) or (number .. ". "))
    if checkbox then continuation = continuation .. "[ ] " end
    return "\n" .. continuation
  end

  local current_indent = line:match("^(%s*)") or ""
  return "\n" .. current_indent
end

function markdown.renumber_ordered_list()
  local bufnr = vim.api.nvim_get_current_buf()
  local current = vim.api.nvim_win_get_cursor(0)[1] - 1
  if current < 0 then
    return
  end
  local line = vim.api.nvim_buf_get_lines(bufnr, current, current + 1, false)[1]
  if not line or not line:match("^%s*%d+%.%s+") then
    return
  end
  local start_line = current
  while start_line > 0 do
    local prev = vim.api.nvim_buf_get_lines(bufnr, start_line - 1, start_line, false)[1]
    if not prev or not prev:match("^%s*%d+%.%s+") then
      break
    end
    start_line = start_line - 1
  end
  local line_count = vim.api.nvim_buf_line_count(bufnr)
  local end_line = current
  while end_line + 1 < line_count do
    local next_line = vim.api.nvim_buf_get_lines(bufnr, end_line + 1, end_line + 2, false)[1]
    if not next_line or not next_line:match("^%s*%d+%.%s+") then
      break
    end
    end_line = end_line + 1
  end
  local numbering = 1
  for line_nr = start_line, end_line do
    local text = vim.api.nvim_buf_get_lines(bufnr, line_nr, line_nr + 1, false)[1]
    local indent, _, rest = text:match("^(%s*)(%d+)%.%s*(.*)$")
    if indent then
      local suffix = rest ~= "" and (" " .. rest) or ""
      vim.api.nvim_buf_set_lines(bufnr, line_nr, line_nr + 1, false, { ("%s%d.%s"):format(indent, numbering, suffix) })
      numbering = numbering + 1
    end
  end
end

function markdown.toggle_spell()
  local new_value = not vim.opt_local.spell:get()
  vim.opt_local.spell = new_value
  if new_value then
    local langs = vim.opt_local.spelllang:get()
    local has_cjk = false
    for _, lang in ipairs(langs) do
      if lang == "cjk" then
        has_cjk = true
        break
      end
    end
    if not has_cjk then
      vim.opt_local.spelllang = { "en_us", "cjk" }
    end
  end
end

vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function(event)
    set_local_indent(2, true)
    local o = vim.opt_local
    o.spell = false
    o.spelllang = { "en_us", "cjk" }
    o.wrap = true
    o.linebreak = true
    o.textwidth = 0
    o.colorcolumn = ""
    o.conceallevel = 2
    o.concealcursor = "nc"
    o.comments = { "fb:*", "fb:-", "fb:+", "n:>" }
    o.commentstring = "<!-- %s -->"
    o.formatlistpat = [[^\s*\d\+\.\s\+\|^\s*[-*+]\s\+\|^\[[^][]\+\]:\&^.\{4\}]]
    vim.bo.autoindent = false
    vim.bo.smartindent = false
    vim.bo.cindent = false
    vim.bo.indentexpr = ""
    o.formatoptions:remove("r")
    o.formatoptions:remove("o")
    o.formatoptions:append("t")
    o.formatoptions:append("c")
    o.formatoptions:append("q")
    o.formatoptions:append("l")
    o.formatoptions:append("n")

    local key_opts = { buffer = event.buf, noremap = true, silent = true }
    vim.keymap.set("n", "<leader>mt", markdown.toggle_checkbox_current, vim.tbl_extend("force", key_opts, { desc = "Toggle checkbox" }))
    vim.keymap.set("x", "<leader>mt", markdown.toggle_checkbox_visual, vim.tbl_extend("force", key_opts, { desc = "Toggle checkbox (visual)" }))
    vim.keymap.set("n", "<leader>mr", markdown.renumber_ordered_list, vim.tbl_extend("force", key_opts, { desc = "Renumber ordered list" }))
    vim.keymap.set("i", "<CR>", markdown.continue_list_newline, vim.tbl_extend("force", key_opts, { expr = true, desc = "Continue Markdown list" }))
    vim.keymap.set("n", "<leader>ms", markdown.toggle_spell, vim.tbl_extend("force", key_opts, { desc = "Toggle spell checking" }))
  end,
})

-- === TFENV + terraform-ls bootstrap (safe, idempotent) ===
if not vim.g.__tfenv_lsp_bootstrap then
  vim.g.__tfenv_lsp_bootstrap = true

  local ok_util, util = pcall(require, "lspconfig.util")
  if ok_util then

    -- Build a safe env that prefers tfenv and enables provider caching
    local function tfenv_env(base)
      local env = {}
      for k, v in pairs(base or {}) do env[k] = v end

      local home = vim.loop.os_homedir()
      -- PATH list separator
      local list_sep = (vim.fn.has("win32") == 1 or vim.fn.has("win64") == 1) and ";" or ":"
      local current_path = env.PATH or os.getenv("PATH") or ""

      local paths = {
        home .. "/.tfenv/shims",
        home .. "/.tfenv/bin",
      }

      -- Prepend if directory exists
      for i = #paths, 1, -1 do
        local p = paths[i]
        if vim.fn.isdirectory(p) == 1 then
          current_path = p .. list_sep .. current_path
        end
      end

      env.PATH = current_path
      env.TFENV_AUTO_INSTALL = "true"
      env.TF_PLUGIN_CACHE_DIR = home .. "/.terraform.d/plugin-cache"
      return env
    end

    -- Reusable cmd_env for terraform-ls
    local cmd_env = tfenv_env({})

    -- Root detection supports 0.12, 0.13, and 1.x layouts
    local root_dir = util.root_pattern(".terraform-version", ".tool-versions", "versions.tf", ".terraform", ".git")

    -- Configure terraform-ls to always use tfenv-backed terraform
    configure_lsp("terraformls", {
      cmd = { "terraform-ls", "serve" },
      cmd_env = cmd_env,
      filetypes = { "terraform", "terraform-vars", "hcl" },
      root_dir = root_dir,
      single_file_support = true,
      settings = {
        terraform = {
          path = "terraform",   -- tfenv shims가 해결
        },
      },
    })

    enable_lsp("terraformls")

    -- Optional inspection commands (no side effects)
    vim.api.nvim_create_user_command("TerraformEnvInfo", function()
      local out = ""
      if vim.fn.has("wsl") == 1 then
        local ok, handle = pcall(io.popen, "bash -lc 'command -v terraform && terraform version | head -n1'")
        if ok and handle then
          out = handle:read("*a") or ""
          handle:close()
        end
      else
        local ok2, handle2 = pcall(io.popen, "terraform version | head -n1 2>&1")
        if ok2 and handle2 then
          out = handle2:read("*a") or ""
          handle2:close()
        end
      end
      if out == "" then out = "terraform not found in PATH" end
      vim.notify(out, vim.log.levels.INFO, { title = "TerraformEnvInfo" })
    end, {})

    vim.api.nvim_create_user_command("TerraformSetEnv", function()
      local new_env = tfenv_env({ PATH = os.getenv("PATH") })
      vim.env.PATH = new_env.PATH
      vim.env.TFENV_AUTO_INSTALL = new_env.TFENV_AUTO_INSTALL
      vim.env.TF_PLUGIN_CACHE_DIR = new_env.TF_PLUGIN_CACHE_DIR
      vim.notify("tfenv environment exported for this Neovim session", vim.log.levels.INFO, { title = "TerraformSetEnv" })
    end, {})
  end
end
-- === End TFENV + terraform-ls bootstrap ===
