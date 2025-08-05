# AGENTS.md

## Instructions for AI Agents Working on Birdman Project

This file provides instructions for AI agents (including OpenAI Codex, Claude Code, GitHub Copilot, etc.) working in this codebase. You MUST follow all instructions in this file.

### Core Project Rules / 核心專案規則

**CRITICAL: Read these documents first, in this order:**
1. `docs/Requirements.md` - Complete technical specifications (MANDATORY READ)
2. `docs/AI_SYNC_README.md` - Current project status, gaps, and pending tasks
3. `docs/AI_LOG.md` - AI operation history and decision log
4. `CLAUDE.md` - Additional guidance for Claude Code agents

**Language Requirements:**
- All code comments, commit messages, PR descriptions, and documentation MUST be in Traditional Chinese (繁體中文)
- Variable names and function names use camelCase
- English is acceptable for international communication but Traditional Chinese is required

### Code Style and Structure / 程式碼風格與結構

**Python Code Standards:**
- Follow PEP 8 with 120 character line limit
- Use type hints for all function parameters and return values
- All docstrings in Traditional Chinese
- Import order: standard library, third-party, local imports

**File Organization:**
- Core modules in `src/` directory
- GUI components in `src/ui/`
- Test files in `tests/` with `test_` prefix
- Sample data in `sample_data/`
- Documentation in `docs/`

**Naming Conventions:**
- Functions: camelCase (e.g., `readDsm`, `buildGraph`)
- Classes: PascalCase (e.g., `TaskProcessor`, `ResourceManager`)
- Constants: UPPER_SNAKE_CASE (e.g., `DEFAULT_CONFIG_PATH`)
- Files: snake_case (e.g., `dsm_processor.py`, `cpm_analysis.py`)

### Technical Architecture / 技術架構

**Core Components (You MUST understand these before making changes):**
- `src/dsm_processor.py`: DSM dependency matrix processing, topological sorting, SCC analysis
- `src/wbs_processor.py`: Work Breakdown Structure processing, task merging by SCC
- `src/cpm_processor.py`: Critical Path Method analysis, Monte Carlo simulation
- `src/rcpsp_solver.py`: Resource-Constrained Project Scheduling with OR-Tools
- `src/visualizer.py`: Graph visualization, Gantt charts, SVG/PNG export
- `src/gui_qt.py`: PyQt5 GUI with tabbed interface and theme switching

**Data Format Requirements:**
- DSM files: N×N matrix, CSV format, UTF-8 encoding
- WBS files: Must include Task_ID, TRF, Property, work time estimates
- Resources files: Group, Hr_Per_Week, Headcount_Cap fields required
- All Task_IDs follow format: `[Property][Year]-[Number]` (e.g., A26-001)

**Task Merging Algorithm:**
- Tasks in same SCC are merged using formula: `k = base + sqrt((ΣTRF / n) * trf_scale / trf_divisor) + n_coef * (n - 1)`
- Merged Task IDs format: `M<Year>-<Number>[<OriginalTaskIDs>]`
- Configuration in `config.json` under `merge_k_params`

### Required Workflow / 必須工作流程

**BEFORE Starting Any Task:**
1. Read `docs/Requirements.md` completely - this contains ALL technical specifications
2. Check `docs/AI_SYNC_README.md` for current status and gaps
3. Review `docs/AI_LOG.md` for recent changes and decisions
4. Understand the specific module you're working on

**DURING Task Execution:**
- Follow the technical specifications in Requirements.md exactly
- Use only the algorithms and data structures specified
- Write all comments and docstrings in Traditional Chinese
- Record any issues or questions in AI_SYNC_README.md

**AFTER Task Completion (MANDATORY):**
1. Update `docs/AI_LOG.md` with summary of changes made
2. Update `docs/AI_SYNC_README.md` with current status and any remaining gaps
3. If you discover specification conflicts, record them in AI_SYNC_README.md with "AI疑問" tag

### Git and PR Requirements / Git 與 PR 要求

**Branch Naming:**
- `feature/[description]` - New features
- `bugfix/[description]` - Bug fixes
- `refactor/[description]` - Code refactoring
- `docs/[description]` - Documentation updates
- `ai/[description]` - AI-generated changes

**Commit Messages (REQUIRED FORMAT):**
```
[type]: [Traditional Chinese description]

[Optional detailed description in Traditional Chinese]

🤖 Generated with [AI Tool Name]

Co-Authored-By: [AI Agent] <noreply@company.com>
```

**PR Requirements:**
- Title and description in Traditional Chinese
- Include summary of changes and rationale
- Reference any related issues or requirements
- Add reviewers before merging

### Testing and Quality Assurance / 測試與品質保證

**MANDATORY: You MUST run these checks after ANY code change:**

```bash
# 1. Run all tests (REQUIRED)
pytest -q

# 2. Check code style for project files only (REQUIRED) 
flake8 src/ tests/ main.py --max-line-length=120

# 3. Verify application still works (REQUIRED)
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json

# 4. Test GUI if GUI changes made (REQUIRED for GUI changes)
python -m src.gui_qt
```

**Quality Requirements:**
- All tests must pass before submitting changes
- Code must pass flake8 linting
- Application must run without errors on sample data
- GUI must launch and function correctly if modified

### Error Handling / 錯誤處理

**If you encounter errors:**
1. Document the error in `docs/AI_SYNC_README.md` under "AI疑問/人工待回覆"
2. Include full error message and steps to reproduce
3. Suggest potential solutions if possible
4. Do not proceed with changes that cause test failures

### File Modification Rules / 檔案修改規則

**Files you can modify freely:**
- Source code in `src/` directory
- Test files in `tests/` directory
- Documentation files in `docs/`
- Configuration in `config.json`

**Files requiring special care:**
- `requirements.txt` - Only add dependencies if absolutely necessary
- `main.py` - Preserve existing CLI interface
- `sample_data/` - Do not modify, these are reference test files

**Files you should NOT modify without explicit instruction:**
- `.gitignore`
- GitHub workflow files in `.github/`
- Project root configuration files

### AI Agent Coordination / AI 代理協調

This project uses multiple AI systems:
- **OpenAI Codex**: Primary code implementation (uses this AGENTS.md as main reference)  
- **Claude Code**: Requirements analysis, code review, problem diagnosis
- **GitHub Copilot**: Code completion assistance

All AI agents must:
1. Follow the same technical specifications in Requirements.md
2. Use the same coding standards defined here
3. Update the documentation files consistently
4. Respect the precedence: Requirements.md > AGENTS.md > other docs
