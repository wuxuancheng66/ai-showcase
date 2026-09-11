# Codex Skills 总览与调用指南

> 生成时间：2026-09-06　|　共发现 **57** 个 Skill（磁盘已装）

## 一、如何调用 Skill

| 环境 | 操作 |
|------|------|
| **桌面 App** | 输入框输入 `@`，弹出列表选择 Skill |
| **Codex CLI / IDE** | 输入 `$` 提及 Skill（如 `$skill-creator`），或运行 `/skills` 查看 |
| **任意环境** | 直接在提示词里点名，如“用 documents 技能生成一份 Word 文档” |

### 2. 隐式调用（自动）

任务描述与 Skill 描述匹配时，Codex 会自动加载该 Skill，无需手动指定。

## 二、全部 Skill 清单

### 个人

1. **code-review**　（💤 磁盘已装）
   - 调用名：`code-review`
   - 用途：Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes — Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the originating issue/spec asked for?). Runs both reviews in parallel sub-agents and reports them side by side. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to "review since X".
   - 位置：`/Users/wuxuancheng/.codex/skills/code-review/SKILL.md`

2. **codebase-design**　（💤 磁盘已装）
   - 调用名：`codebase-design`
   - 用途：Shared vocabulary for designing deep modules. Use when the user wants to design or improve a module's interface, find deepening opportunities, decide where a seam goes, make code more testable or AI-navigable, or when another skill needs the deep-module vocabulary.
   - 位置：`/Users/wuxuancheng/.codex/skills/codebase-design/SKILL.md`

3. **diagnosing-bugs**　（💤 磁盘已装）
   - 调用名：`diagnosing-bugs`
   - 用途：Diagnosis loop for hard bugs and performance regressions. Use when the user says "diagnose"/"debug this", or reports something broken/throwing/failing/slow.
   - 位置：`/Users/wuxuancheng/.codex/skills/diagnosing-bugs/SKILL.md`

4. **domain-modeling**　（💤 磁盘已装）
   - 调用名：`domain-modeling`
   - 用途：Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing a CONTEXT.md, or recording or editing an ADR.
   - 位置：`/Users/wuxuancheng/.codex/skills/domain-modeling/SKILL.md`

5. **goal-agent-team**　（💤 磁盘已装）
   - 调用名：`goal-agent-team`
   - 用途：Align requirements into one source of truth, then run autonomous goal planning and agent-team execution. Use when Codex should clarify, document, and then execute end to end with minimal interruption.
   - 位置：`/Users/wuxuancheng/.codex/skills/goal-agent-team/SKILL.md`

6. **goal-agent-team-auto**　（💤 磁盘已装）
   - 调用名：`goal-agent-team-auto`
   - 用途：Align the task into one source of truth, then execute autonomously with goal planning, agent-team delegation, and verification loops. Use when Codex should run end to end with near-zero supervision.
   - 位置：`/Users/wuxuancheng/.codex/skills/goal-agent-team-auto/SKILL.md`

7. **hallmark**　（💤 磁盘已装）
   - 调用名：`hallmark`
   - 用途：Anti-AI-slop design skill for greenfield pages, audits, redesigns, and design extraction from URLs or screenshots. Use when the user asks to build a new app or landing page, wants to redesign something, invokes Hallmark by name, or uses audit/redesign/study.
   - 位置：`/Users/wuxuancheng/.codex/skills/hallmark/SKILL.md`

8. **implement**　（💤 磁盘已装）
   - 调用名：`implement`
   - 用途：Implement a piece of work based on a spec or set of tickets.
   - 位置：`/Users/wuxuancheng/.codex/skills/implement/SKILL.md`

9. **manual-refresher**　（💤 磁盘已装）
   - 调用名：`manual-refresher`
   - 用途：刷新《Codex GPT 全面掌握手册》：核验 Codex 配置与已装技能/插件，更新手册第 2/5/23 章与版本记录，重新生成 HTML，并同步到 AI知识库与 Obsidian。当用户说"刷新手册""更新手册""核验配置"时使用。
   - 位置：`/Users/wuxuancheng/.codex/skills/manual-refresher/SKILL.md`

10. **prototype**　（💤 磁盘已装）
   - 调用名：`prototype`
   - 用途：Build a throwaway prototype to answer a design question. Use when the user wants to sanity-check whether a state model or logic feels right, or explore what a UI should look like.
   - 位置：`/Users/wuxuancheng/.codex/skills/prototype/SKILL.md`

11. **research**　（💤 磁盘已装）
   - 调用名：`research`
   - 用途：Investigate a question against high-trust primary sources and capture the findings as a Markdown file in the repo. Use when the user wants a topic researched, docs or API facts gathered, or reading legwork delegated to a background agent.
   - 位置：`/Users/wuxuancheng/.codex/skills/research/SKILL.md`

12. **resolving-merge-conflicts**　（💤 磁盘已装）
   - 调用名：`resolving-merge-conflicts`
   - 用途：Use when you need to resolve an in-progress git merge/rebase conflict.
   - 位置：`/Users/wuxuancheng/.codex/skills/resolving-merge-conflicts/SKILL.md`

13. **tdd**　（💤 磁盘已装）
   - 调用名：`tdd`
   - 用途：Test-driven development. Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants integration tests.
   - 位置：`/Users/wuxuancheng/.codex/skills/tdd/SKILL.md`

### 系统

14. **imagegen**　（💤 磁盘已装）
   - 调用名：`imagegen`
   - 用途：Generate or edit raster images when the task benefits from AI-created bitmap visuals such as photos, illustrations, textures, sprites, mockups, or transparent-background cutouts. Use when Codex should create a brand-new image, transform an existing image, or derive visual variants from references, and the output should be a bitmap asset rather than repo-native code or vector. Do not use when the task is better handled by editing existing SVG/vector/code-native assets, extending an established icon or logo system, or building the visual directly in HTML/CSS/canvas.
   - 位置：`/Users/wuxuancheng/.codex/skills/.system/imagegen/SKILL.md`

15. **openai-docs**　（💤 磁盘已装）
   - 调用名：`openai-docs`
   - 用途：Use for Codex models/pricing, scheduled tasks, skills, settings, setup, troubleshooting, customization, automations, and self-knowledge—including 'you,' 'your,' 'this app,' or 'this coding agent' when they refer to Codex—and for OpenAI APIs/products and ChatGPT Work. Also use for model choice/migration, prompting, SDKs, Responses, Realtime, agents, evals, and Chat/Work/Codex comparisons. Do not use for generic app/software tasks that merely mention Codex.
   - 位置：`/Users/wuxuancheng/.codex/skills/.system/openai-docs/SKILL.md`

16. **plugin-creator**　（💤 磁盘已装）
   - 调用名：`plugin-creator`
   - 用途：Create and scaffold plugin directories for Codex with a required `.codex-plugin/plugin.json`, optional plugin folders/files, valid manifest defaults, and personal-marketplace entries by default. Use when Codex needs to create a new personal plugin, add optional plugin structure, generate or update marketplace entries for plugin ordering and availability metadata, or update an existing local plugin during development with the CLI-driven cachebuster and reinstall flow.
   - 位置：`/Users/wuxuancheng/.codex/skills/.system/plugin-creator/SKILL.md`

17. **review-agent**　（💤 磁盘已装）
   - 调用名：`review-agent`
   - 用途：Perform a read-only, defect-first review of a specified code change and return every actionable finding. Use when another agent delegates review of uncommitted changes, a base-branch diff, a commit, or custom review instructions.
   - 位置：`/Users/wuxuancheng/.codex/skills/.system/review-agent/SKILL.md`

18. **skill-creator**　（💤 磁盘已装）
   - 调用名：`skill-creator`
   - 用途：Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Codex's capabilities with specialized knowledge, workflows, or tool integrations.
   - 位置：`/Users/wuxuancheng/.codex/skills/.system/skill-creator/SKILL.md`

19. **skill-installer**　（💤 磁盘已装）
   - 调用名：`skill-installer`
   - 用途：Install Codex skills into $CODEX_HOME/skills from a curated list or a GitHub repo path. Use when a user asks to list installable skills, install a curated skill, or install a skill from another repo (including private repos).
   - 位置：`/Users/wuxuancheng/.codex/skills/.system/skill-installer/SKILL.md`

### 插件·browser

20. **control-in-app-browser**　（💤 磁盘已装）
   - 调用名：`control-in-app-browser`
   - 用途：Control the in-app Browser for opening, navigating, inspecting visible or interactive page state, clicking, typing, screenshots, and local web testing. It can have existing signed-in sessions. For semantic operations on linked resources, prefer a purpose-built connector, API, or CLI when available.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-bundled/browser/26.803.41515/skills/control-in-app-browser/SKILL.md`

### 插件·build-web-apps

21. **frontend-app-builder**　（💤 磁盘已装）
   - 调用名：`frontend-app-builder`
   - 用途：Use for new frontend applications, dashboards, games, creative websites, hero sections, and visually driven UI from scratch, or when the user explicitly asks for a redesign/restyle/modernization. Builds from clean, airy, high-taste, readable image-generated concept design with section-specific references, faithful implementation, and browser testing.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/build-web-apps/11c74d6b/skills/frontend-app-builder/SKILL.md`

22. **frontend-testing-debugging**　（💤 磁盘已装）
   - 调用名：`frontend-testing-debugging`
   - 用途：Use when testing, debugging, or making targeted improvements to rendered frontend apps through the Build Web Apps or web dev plugin: local dev servers, UI regressions, interaction bugs, console errors, responsive layout, and visual QA. Check whether the Browser plugin is available and use it first when it is; otherwise use regular Playwright with the recorded reason.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/build-web-apps/11c74d6b/skills/frontend-testing-debugging/SKILL.md`

23. **react-best-practices**　（💤 磁盘已装）
   - 调用名：`react-best-practices`
   - 用途：React and Next.js performance optimization guidelines from Vercel Engineering. This skill should be used when writing, reviewing, or refactoring React/Next.js code to ensure optimal performance patterns. Triggers on tasks involving React components, Next.js pages, data fetching, bundle optimization, or performance improvements.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/build-web-apps/11c74d6b/skills/react-best-practices/SKILL.md`

24. **shadcn-best-practices**　（💤 磁盘已装）
   - 调用名：`shadcn-best-practices`
   - 用途：Manages shadcn components and projects — adding, searching, fixing, debugging, styling, and composing UI. Provides project context, component docs, and usage examples. Applies when working with shadcn/ui, component registries, presets, --preset codes, or any project with a components.json file. Also triggers for "shadcn init", "create an app with --preset", or "switch to --preset".
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/build-web-apps/11c74d6b/skills/shadcn-best-practices/SKILL.md`

25. **stripe-best-practices**　（💤 磁盘已装）
   - 调用名：`stripe-best-practices`
   - 用途：Guides Stripe integration decisions — API selection (Checkout Sessions vs PaymentIntents), Connect platform setup (Accounts v2, controller properties), billing/subscriptions, Treasury financial accounts, integration surfaces (Checkout, Payment Element), and migrating from deprecated Stripe APIs. Use when building, modifying, or reviewing any Stripe integration — including accepting payments, building marketplaces, integrating Stripe, processing payments, setting up subscriptions, or creating connected accounts.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/build-web-apps/11c74d6b/skills/stripe-best-practices/SKILL.md`

26. **supabase-best-practices**　（💤 磁盘已装）
   - 调用名：`supabase-best-practices`
   - 用途：Postgres performance optimization and best practices from Supabase. Use this skill when writing, reviewing, or optimizing Postgres queries, schema designs, or database configurations.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/build-web-apps/11c74d6b/skills/supabase-best-practices/SKILL.md`

### 插件·chrome

27. **control-chrome**　（💤 磁盘已装）
   - 调用名：`control-chrome`
   - 用途：Control the user's Chrome browser for tasks that depend on existing Chrome state: tabs, logged-in sessions, or extensions. Prefer purpose-built connectors, APIs, or CLIs when available.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-bundled/chrome/26.803.41515/skills/control-chrome/SKILL.md`

### 插件·computer-use

28. **computer-use**　（💤 磁盘已装）
   - 调用名：`computer-use`
   - 用途：Control local Mac apps through Computer Use for tasks that require reading or operating app UI. Prefer purpose-built connectors, APIs, or CLIs when available.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-bundled/computer-use/1.0.1000633/skills/computer-use/SKILL.md`

### 插件·documents

29. **documents**　（💤 磁盘已装）
   - 调用名：`documents`
   - 用途：Create, edit, redline, and comment on `.docx`, Word, and Google Docs-targeted document artifacts inside the container, with a strict render-and-verify workflow. Use `render_docx.py` to generate page PNGs (and optional PDF) for visual QA, then iterate until layout is flawless before delivering the final document.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-primary-runtime/documents/26.904.11930/skills/documents/SKILL.md`

### 插件·figma

30. **figma-code-connect**　（💤 磁盘已装）
   - 调用名：`figma-code-connect`
   - 用途：Creates and maintains Figma Code Connect template files that map Figma components to code snippets. Use when the user mentions Code Connect, Figma component mapping, design-to-code translation, or asks to create/update .figma.ts or .figma.js files.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-code-connect/SKILL.md`

31. **figma-create-new-file**　（💤 磁盘已装）
   - 调用名：`figma-create-new-file`
   - 用途：**MANDATORY prerequisite** — you MUST invoke this skill BEFORE every `create_new_file` tool call. NEVER call `create_new_file` directly without loading this skill first. Trigger whenever the user wants a new blank Figma file — a new design, FigJam, or Slides file — or when you need a fresh file before calling `use_figma`. Usage — /figma-create-new-file [editorType] [fileName] (e.g. /figma-create-new-file figjam My Whiteboard, /figma-create-new-file slides Q3 Review)
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-create-new-file/SKILL.md`

32. **figma-design-to-code**　（💤 磁盘已装）
   - 调用名：`figma-design-to-code`
   - 用途：Use this skill when implementing a Figma design as code (design → code) — the read-FROM-Figma direction. Triggers: 'implement this Figma design', 'build this screen from Figma', 'turn this Figma into code', 'code this up from Figma', 'design to code', or a figma.com design URL provided alongside a codebase. Encodes the workflow for reading a node out of Figma with get_design_context and adapting its reference output to the target project — reusing existing components, tokens, and conventions, and honoring Code Connect mappings, component docs, design annotations, and design tokens by priority. Complements figma-code-connect (component mapping) and figma-generate-design / figma-use (the reverse, code → design direction).
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-design-to-code/SKILL.md`

33. **figma-generate-design**　（💤 磁盘已装）
   - 调用名：`figma-generate-design`
   - 用途：Use this skill alongside figma-use when the task involves translating an application page, view, or multi-section layout into Figma. Triggers: 'write to Figma', 'create in Figma from code', 'push page to Figma', 'take this app/page and build it in Figma', 'create a screen', 'build a landing page in Figma', 'update the Figma screen to match code', 'convert this modal/dialog/drawer/panel to Figma'. This is the preferred workflow skill whenever the user wants to build or update a full page, modal, dialog, drawer, sidebar, panel, or any composed multi-section view in Figma from code or a description. Discovers design system components, variables, and styles from Code Connect files, existing screens, and library search, then imports them and assembles views incrementally section-by-section using design system tokens instead of hardcoded values.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-generate-design/SKILL.md`

34. **figma-generate-diagram**　（💤 磁盘已装）
   - 调用名：`figma-generate-diagram`
   - 用途：MANDATORY prerequisite — load this skill BEFORE every `generate_diagram` tool call. NEVER call `generate_diagram` directly without loading this skill first. Trigger whenever the user asks to create, generate, draw, render, sketch, or build a diagram — flowchart, architecture diagram, sequence diagram, ERD or entity-relationship diagram, state diagram or state machine, gantt chart, or timeline. Also trigger when the user mentions Mermaid syntax or wants a system architecture, decision tree, dependency graph, API call flow, auth handshake, schema, or pipeline visualized in FigJam. Routes to type-specific guidance, sets universal Mermaid constraints, and tells you when to use a different diagram type or skip the tool entirely (mindmaps, pie charts, class diagrams, etc.).
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-generate-diagram/SKILL.md`

35. **figma-generate-library**　（💤 磁盘已装）
   - 调用名：`figma-generate-library`
   - 用途：Build or update a professional-grade design system in Figma from a codebase. Use when the user wants to create variables/tokens, build component libraries, create individual components with proper variant sets and variable bindings, set up theming (light/dark modes), document foundations, or reconcile gaps between code and Figma. Also use when the user asks to create or generate any component in Figma — even a single one — since components require proper variable foundations, variant states, and design token bindings to be production-quality. This skill teaches WHAT to build and in WHAT ORDER — it complements the `figma-use` skill which teaches HOW to call the Plugin API. Both skills should be loaded together.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-generate-library/SKILL.md`

36. **figma-implement-motion**　（💤 磁盘已装）
   - 调用名：`figma-implement-motion`
   - 用途：Translates Figma motion and animations into production-ready application code. Use when implementing animation/motion from a Figma design — user mentions "implement this motion", "add animation from Figma", "animate this component", provides a Figma URL whose node is animated, or when `get_design_context` returns motion data or instructs you to call `get_motion_context`.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-implement-motion/SKILL.md`

37. **figma-swiftui**　（💤 磁盘已装）
   - 调用名：`figma-swiftui`
   - 用途：SwiftUI ↔ Figma translation. Use whenever the user mentions Swift, SwiftUI, iOS, iPhone, or iPad — in EITHER direction — translating a Figma design into SwiftUI (design → code), or pushing SwiftUI views / screens / tokens back into a Figma file (code → design). Triggers on phrases like 'implement this Figma design in SwiftUI', 'build this screen in Swift', 'push this SwiftUI view to Figma', 'mirror my Swift code in a Figma file', or whenever a Figma URL appears alongside `.swift` files / an `.xcodeproj`. Routes to a direction-specific reference doc; loads alongside `figma-use` for the code → design path.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-swiftui/SKILL.md`

38. **figma-use**　（💤 磁盘已装）
   - 调用名：`figma-use`
   - 用途：**MANDATORY prerequisite** — you MUST invoke this skill BEFORE every `use_figma` tool call. NEVER call `use_figma` directly without loading this skill first. Skipping it causes common, hard-to-debug failures. Trigger whenever the user wants to perform a write action or a unique read action that requires JavaScript execution in the Figma file context — e.g. create/edit/delete nodes, set up variables or tokens, build components and variants, modify auto-layout or fills, bind variables to properties, or inspect file structure programmatically.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-use/SKILL.md`

39. **figma-use-figjam**　（💤 磁盘已装）
   - 调用名：`figma-use-figjam`
   - 用途：This skill helps agents use Figma's use_figma MCP tool in the FigJam context. Can be used alongside figma-use which has foundational context for using the use_figma tool.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-use-figjam/SKILL.md`

40. **figma-use-motion**　（💤 磁盘已装）
   - 调用名：`figma-use-motion`
   - 用途：Motion / animation context for the `use_figma` MCP tool — animating Figma nodes via manual keyframes, animation styles, easing, and timeline duration. Load alongside figma-use whenever a task involves adding, editing, or inspecting animation on a node.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-use-motion/SKILL.md`

41. **figma-use-slides**　（💤 磁盘已装）
   - 调用名：`figma-use-slides`
   - 用途：This skill helps agents use Figma's use_figma MCP tool in the Slides context. Can be used alongside figma-use which has foundational context for using the use_figma tool.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/figma/11c74d6b/skills/figma-use-slides/SKILL.md`

### 插件·github

42. **gh-address-comments**　（💤 磁盘已装）
   - 调用名：`gh-address-comments`
   - 用途：Address actionable GitHub pull request review feedback. Use when the user wants to inspect unresolved review threads, requested changes, or inline review comments on a PR, then implement selected fixes. Use the GitHub app for PR metadata and flat comment reads, and use the bundled GraphQL script via `gh` whenever thread-level state, resolution status, or inline review context matters.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/github/11c74d6b/skills/gh-address-comments/SKILL.md`

43. **gh-fix-ci**　（💤 磁盘已装）
   - 调用名：`gh-fix-ci`
   - 用途：Use when a user asks to debug or fix failing GitHub PR checks that run in GitHub Actions. Use the GitHub app from this plugin for PR metadata and patch context, and use `gh` for Actions check and log inspection before implementing any approved fix.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/github/11c74d6b/skills/gh-fix-ci/SKILL.md`

44. **github**　（💤 磁盘已装）
   - 调用名：`github`
   - 用途：Triage and orient GitHub repository, pull request, and issue work through the connected GitHub app. Use when the user asks for general GitHub help, wants PR or issue summaries, or needs repository context before choosing a more specific GitHub workflow.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/github/11c74d6b/skills/github/SKILL.md`

45. **yeet**　（💤 磁盘已装）
   - 调用名：`yeet`
   - 用途：Publish local changes to GitHub by confirming scope, committing intentionally, pushing the branch, and opening a draft PR through the GitHub app from this plugin, with `gh` used only as a fallback where connector coverage is insufficient.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/github/11c74d6b/skills/yeet/SKILL.md`

### 插件·linear

46. **linear**　（💤 磁盘已装）
   - 调用名：`linear`
   - 用途：Manage issues, projects & team workflows in Linear. Use when the user wants to read, create or updates tickets in Linear.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/linear/11c74d6b/skills/linear/SKILL.md`

### 插件·neon-postgres

47. **neon-postgres**　（💤 磁盘已装）
   - 调用名：`neon-postgres`
   - 用途：Guides and best practices for working with Neon Serverless Postgres. Covers getting started, local development with Neon, choosing a connection method, Neon features, authentication (@neondatabase/auth), PostgREST-style data API (@neondatabase/neon-js), Neon CLI, and Neon's Platform API/SDKs. Use for any Neon-related questions.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/neon-postgres/11c74d6b/skills/neon-postgres/SKILL.md`

48. **neon-postgres-egress-optimizer**　（💤 磁盘已装）
   - 调用名：`neon-postgres-egress-optimizer`
   - 用途：>-
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/neon-postgres/11c74d6b/skills/neon-postgres-egress-optimizer/SKILL.md`

### 插件·pdf

49. **pdf**　（💤 磁盘已装）
   - 调用名：`pdf`
   - 用途：Read, create, inspect, render, and verify PDF files where visual layout matters, including fillable AcroForms. Use Poppler rendering plus Python tools such as reportlab, pdfplumber, and pypdf for generation and extraction.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-primary-runtime/pdf/26.904.11930/skills/pdf/SKILL.md`

### 插件·presentations

50. **presentations**　（💤 磁盘已装）
   - 调用名：`presentations`
   - 用途：Read, create or edit PowerPoint or Google Slides decks. Use for presentation, slide deck, PowerPoint, PPT, PPTX, or Google Slides requests.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations/SKILL.md`

### 插件·sentry

51. **sentry**　（💤 磁盘已装）
   - 调用名：`sentry`
   - 用途：Use when the user asks to inspect Sentry issues or events, summarize recent production errors, or pull basic Sentry health data via the Sentry API; perform read-only queries with the bundled script and require `SENTRY_AUTH_TOKEN`.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/sentry/11c74d6b/skills/sentry/SKILL.md`

### 插件·spreadsheets

52. **excel-live-control**　（💤 磁盘已装）
   - 调用名：`excel-live-control`
   - 用途：Control an open or active Microsoft Excel workbook through the ChatGPT add-in or connected session. Use when the user tags the Microsoft Excel app in Codex or follows up on an established live Excel task. Do not use for standalone spreadsheet files or Google Sheets.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-primary-runtime/spreadsheets/26.904.11930/skills/excel-live-control/SKILL.md`

53. **spreadsheets**　（💤 磁盘已装）
   - 调用名：`spreadsheets`
   - 用途：Create, edit, analyze, and verify standalone spreadsheet files or Google Sheets-ready workbooks, including .xlsx, .xls, .csv, and .tsv. Do not use for live controlling Microsoft Excel app or a live Excel session.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-primary-runtime/spreadsheets/26.904.11930/skills/spreadsheets/SKILL.md`

### 插件·supabase

54. **supabase**　（💤 磁盘已装）
   - 调用名：`supabase`
   - 用途：Use when doing ANY task involving Supabase. Triggers: Supabase products (Database, Auth, Edge Functions, Realtime, Storage, Vectors, Cron, Queues); client libraries and SSR integrations (supabase-js, @supabase/ssr) in Next.js, React, SvelteKit, Astro, Remix; auth issues (login, logout, sessions, JWT, cookies, getSession, getUser, getClaims, RLS); Supabase CLI or MCP server; schema changes, migrations, security audits, Postgres extensions (pg_graphql, pg_cron, pg_vector).
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/supabase/11c74d6b/skills/supabase/SKILL.md`

55. **supabase-postgres-best-practices**　（💤 磁盘已装）
   - 调用名：`supabase-postgres-best-practices`
   - 用途：Postgres performance optimization and best practices from Supabase. Use this skill when writing, reviewing, or optimizing Postgres queries, schema designs, or database configurations.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-curated/supabase/11c74d6b/skills/supabase-postgres-best-practices/SKILL.md`

### 插件·template-creator

56. **template-creator**　（💤 磁盘已装）
   - 调用名：`template-creator`
   - 用途：Create or update a reusable personal Codex artifact-template skill. Use when the user invokes $template-creator or asks in natural language to create a reusable template from a reference document, presentation, spreadsheet, Google Docs, Slides, or Sheets link, ImageGen or Product Design image, email, Slack message, or Site project, or explicitly asks to edit or update a passed artifact-template skill. Do not use for one-off creation from an existing template.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-primary-runtime/template-creator/26.904.11930/skills/template-creator/SKILL.md`

### 插件·visualize

57. **visualize**　（💤 磁盘已装）
   - 调用名：`visualize`
   - 用途：Create visualizations and interactive tools directly in conversation. Use when asked to show how something works, make simulators or labs, maps, plots, charts or graphs, comparisons, UI mockups, scenarios, adjustable inputs, and exploration beyond regular text.
   - 位置：`/Users/wuxuancheng/.codex/plugins/cache/openai-bundled/visualize/1.0.20/skills/visualize/SKILL.md`

## 三、图例与说明

- **个人 Skills**：位于 `~/.codex/skills/`，随 Codex 自动加载。
- **系统内置**：位于 `~/.codex/skills/.system/`，随 Codex 自带，勿改动。
- **插件技能**：位于插件缓存，插件启用并登录对应服务后，新会话即可用。
- **自动刷新**：`manual-refresher` 技能/每周自动化会重新扫描本清单并同步进《Codex GPT 全面掌握手册》第 23 章。
