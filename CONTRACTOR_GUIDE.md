# Contractor Guide: Adding New Verilog Problems

## 📋 What You're Building and Why

You're creating **Verilog RTL design and verification tasks** for reinforcement learning (RL) training. These tasks will be used to train AI agents to write hardware description l\
## 🚀 Getting Started: Clone the Framework

**BEFORE YOU DO ANYTHING ELSE**, clone the verilog evaluation framework:

```bash
# Navigate to your working directory
cd ~/Documents/GitHub

# Clone the evaluation framework
git clone https://github.com/phinitylabs/verilog-coding-template.git

# Navigate into it
cd verilog-coding-template

# Look around
ls -la
```

**What you just cloned:**
- `Dockerfile` - Builds isolated Docker containers for each problem
- `src/hud_controller/` - Framework code that manages problem setup and grading
- `src/hud_controller/problems/basic.py` - Where you register your problems
- `utils/imagectl3.py` - Build/validate tool (you'll use this A LOT)
- `local-hud.json` - Generated config file for running evaluations
- `README.md` - Framework documentation

---

> ⚠️ **IMPORTANT: Synthesis Checking is REQUIRED**
> 
> All problems MUST have synthesis checking enabled. This ensures agent-generated RTL is synthesizable for real FPGA/ASIC hardware, not just simulatable.
> 
> Always set these parameters in every ProblemSpec:
> - `check_synthesis=True`
> - `synth_top_module="your_module_name"`
> - `synth_target="generic"` (or specific FPGA target)

---

## 📦 Prerequisites

Before you start, make sure you have:

### Required Software:
- **Git** (2.0+): https://git-scm.com
- **Docker Desktop** (20.0+): https://www.docker.com/products/docker-desktop
- **Python** (3.10+): https://www.python.org
- **uv** (Python package manager): Install with `pip install uv`

### Verify Installation:
```bash
git --version        # Should show Git 2.x
docker --version     # Should show Docker 20.x+
python3 --version    # Should show Python 3.10+
uv --version         # Should show uv version
```

### Make sure Docker is running:
```bash
docker ps
# Should show container list (may be empty, that's fine)
# If error, start Docker Desktop application
```

---

## 🔧 Initial Setup

### Step 1: Install Framework Dependencies

```bash
cd ~/Documents/GitHub/verilog-coding-template

# Install all dependencies
uv sync

# This installs:
# - cocotb (Verilog testing framework)
# - pytest (Python testing)
# - Docker Python SDK
# - HUD controller dependencies
```

**Expected output:** Should install ~20-30 packages without errors.

### Step 2: Verify Installation

```bash
# Test that imagectl3 works
uv run utils/imagectl3.py --help

# Should show usage information
```

### Step 3: Understand the Example Problem (Optional but Recommended)

```bash
# Look at the example problem registry
cat src/hud_controller/problems/basic.py

# You'll see example problems like "simple_counter"
# This shows the format you'll use for your problems
```

---

## Overview

Adding a new problem involves:
1. **Initial Setup** - Clone framework and install dependencies (done above!)
2. Creating a problem repository with the correct structure (`sources/` and `tests/`)
3. Creating only three git branches (baseline, test, golden)
4. Registering the problem in the framework
5. Building and validating the Docker images
6. Running HUD evaluations to measure difficulty

**Time estimate:** 
- Initial setup: 15 minutes (one-time, done above!)
- Per problem: 45-90 minutes

**IMPORTANT:** If you are stuck for more than 15 minutes on any part, email sonya@phinity.ai. Don't waste your time debugging HUD setup!

---

## 🤖 API Keys (Optional - Only for Running AI Agents)

**NOTE:** You do NOT need API keys to build and validate problems. API keys are only needed if you want to run AI agents on your tasks.

For building and validating (which is most of your work), you can skip this section entirely.

### If You Want to Run AI Agents Later:

HUD can run AI agents from providers like Anthropic (Claude), OpenAI (GPT), or Google (Gemini). You'll need an API key:

**Anthropic (Claude):**
```bash
# Get key from: https://console.anthropic.com
hud set ANTHROPIC_API_KEY sk-ant-your-key-here
```

**OpenAI (GPT):**
```bash
# Get key from: https://platform.openai.com
hud set OPENAI_API_KEY sk-your-key-here

# Or set as environment variable (Windows PowerShell):
$env:OPENAI_API_KEY="sk-your-key-here"

# Or set as environment variable (Linux/Mac):
export OPENAI_API_KEY="sk-your-key-here"
```

**Google (Gemini):**
```bash
# Get key from: https://aistudio.google.com/app/apikey
hud set GEMINI_API_KEY your-gemini-key-here

# Or set as environment variable (Windows PowerShell):
$env:GEMINI_API_KEY="your-gemini-key-here"

# Or set as environment variable (Linux/Mac):
export GEMINI_API_KEY="your-gemini-key-here"
```

**Note:** gpt-5.2-codex uses `bash` tool (not `shell`) - this is already configured in the framework. The tool mapping has been fixed to use `bash` for OpenAI agents. Gemini also uses `bash` and `str_replace_based_edit_tool` tools.

**Cost warning:** Running agents costs ~$3-5 per task evaluation. Budget accordingly!

---

## ⚠️ CRITICAL REQUIREMENTS (Read This First!)

### 1. **Directory Structure MUST Match Stock Problems**

Your problem repository MUST use these exact directory names:

```
your-problem-repo/
├── sources/          # ✅ RTL files go here (NOT rtl/)
│   ├── module1.sv
│   └── module2.sv
├── tests/            # ✅ Test files go here (NOT harness/ or test/)
│   └── test_problem.py
├── docs/             # Optional: specifications
├── pyproject.toml    # Python dependencies
└── README.md
```

You must preserve the original subdirectory structure inside sources, not deleting the files unrelevant to the current problem. (Full context of the problem should be visible to the agent)

Eg:
```
your-problem-repo/
├── sources/          # ✅ RTL files go here (NOT rtl/)
│   ├── hw
│        ├── module1.sv
│        └── module2.sv
│   ├── libs
│        ├── lib1.sv
│        └── lib2.sv
├── tests/            # ✅ Test files go here (NOT harness/ or test/)
│   └── test_problem.py
├── docs/             # Optional: specifications
├── pyproject.toml    # Python dependencies
└── README.md
```


**❌ WRONG directory names that will cause failures:**
- `rtl/` instead of `sources/`
- `harness/` instead of `tests/`
- `test/` instead of `tests/`
⚠️ CRITICAL - There should not be a `harness/` or `rtl/` in the final branches at all

**Why this matters:** The cocotb_tools.runner expects this structure and will fail to find files otherwise.

### 2. **Every Test File MUST Have a Pytest Wrapper Function**

Your test file needs BOTH cocotb tests AND a pytest wrapper:

```python
import cocotb
from cocotb.triggers import Timer

# ✅ Cocotb tests
@cocotb.test()
async def test_something(dut):
    await Timer(10, unit="ns")
    assert dut.output.value == expected_value

# ✅ REQUIRED: Pytest wrapper at the end
def test_problem_runner():
    import os
    from pathlib import Path
    from cocotb_tools.runner import get_runner
    
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    
    sources = [
        proj_path / "sources/your_module.sv",  # Note: sources/ not rtl/
    ]
    
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="your_module",
        always=True,
    )
    
    runner.test(hdl_toplevel="your_module", test_module="test_problem")
```

**Without the pytest wrapper:**
- Pytest output: `collected 0 items`
- Tests never run
- Validation will fail
- You'll waste hours debugging

**With the wrapper:**
- Pytest output: `collected 1 item` 
- Tests run successfully
- Validation passes

### 3. **Test Expected Values Must Match Golden Implementation**

Your hidden tests must expect the values that your **golden implementation** actually produces:

1. Run your golden implementation
2. Record actual outputs
3. Use those as expected values in tests

```python
# ❌ WRONG: Using arbitrary expected values
assert dut.c.value == 0x1234  # Random value you made up

# ✅ CORRECT: Using values from golden implementation
assert dut.c.value == 0x9530  # Value golden actually produces
```

---

### 4. **⚠️ CRITICAL: Tests MUST NOT Be in Baseline or Golden Branches**

**This is the #1 cause of agent contamination and validation failures!**

The agent must NEVER see test files during development. If the baseline branch contains ANY test files that reference hidden test modules, the agent will try to create those missing modules, contaminating the solution.

**❌ WRONG - This will break agent evaluation:**
```
baseline_branch/
├── sources/module.v
└── tests/
    └── test_module.py  # ← References hidden module = AGENT WILL CREATE IT!
```

**✅ CORRECT - Agent can't see tests:**
```
baseline_branch/
├── sources/module.v
└── (no tests directory at all)

test_branch/
├── sources/module.v
└── tests/
    ├── test_module.py
    └── test_module_hidden.py  # ← Hidden tests only in test branch

golden_branch/
├── sources/module.v  # ← Complete solution
└── (no tests directory)
```

**Why This Matters:**

1. **Agent sees reference to hidden module** → Gets `ModuleNotFoundError`
2. **Agent tries to be helpful** → Creates the "missing" test file
3. **Agent's solution is contaminated** → Now includes test infrastructure code
4. **Grading fails** → You're testing if agent can write tests, not implement modules!

**How to Check:**
```bash
# These should show NO tests directory:
git checkout <problem>_baseline && ls -la
git checkout <problem>_golden && ls -la

# Only this should have tests:
git checkout <problem>_test && ls -la tests/
```

**Reference the RC5 problem for the correct pattern:**
- Baseline: No tests directory
- Test: Complete test suite (runner + hidden tests)
- Golden: No tests directory

---

## 🤖 Using This Guide with Cursor AI

**Great news!** This guide is designed to work seamlessly with Cursor AI. Cursor can automate most of the repetitive steps.

### How to Use with Cursor - Pick Opus 4.5 as model:

1. **Open your problem directory and this guide in Cursor:**
   ```bash
   cursor /path/to/your-problem-directory
   # Also open CONTRACTOR_GUIDE.md in Cursor
   ```

2. **Add files to Cursor context:**
   - Click the "+" button in Cursor chat
   - Add `CONTRACTOR_GUIDE.md`
   - Add your problem directory (all files)

3. **Use this prompt template:**
   ```
   I have a new Verilog problem that needs to be converted to HUD format.
   
   Problem location: [YOUR_PATH_HERE]
   Problem structure:
   - Golden solutions in: harness/patch/rtl/
   - Hidden tests in: harness/test/
   - Spec in: docs/Specification.md
   - Prompt in: prompt.txt
   
   Please follow CONTRACTOR_GUIDE.md step-by-step to:
   1. Convert to HUD format (sources/ and tests/)
   2. Add pytest wrapper to tests
   3. Verify golden solution passes tests
   4. Create three branches (baseline, test, golden)
   5. Copy to framework and register
   6. Build and validate

   ```

4. **What Cursor will do automatically:**
   - ✅ Create directory structure
   - ✅ Copy files to correct locations
   - ✅ Add pytest wrapper to test files
   - ✅ Create git branches
   - ✅ Update Dockerfile and basic.py
   - ✅ Run build and validation commands

### Example Cursor Session:

```
You: "I have problem7 at /Users/me/problems/problem7_rc5/. 
     Follow CONTRACTOR_GUIDE.md to convert it."

Cursor: "I'll help you convert this problem. Let me start by creating 
        the local repository structure..."
        [Creates verilog-problems repo]
        [Copies files]
        [Adds pytest wrapper]
        
Cursor: "Here's the pytest wrapper I added. Please verify the sources 
        list includes all .sv files..."

You: "Looks good! Continue."

Cursor: [Creates branches]
        [Registers in framework]
        [Builds Docker image]
        [Runs validation]
        
Cursor: "✅ Validation passed! All 6 checks successful."
```

### Tips for Best Results:

1. **Be specific about file locations** - Tell Cursor exactly where your harness/, docs/, etc. are
2. **Review the pytest wrapper** - This is the #1 source of errors
3. **Check validation output carefully** - If any check fails, fix before proceeding
4. **One problem at a time** - Don't try to convert multiple problems simultaneously

---

## Part 1: Understanding the Branch Structure

Each problem requires **3 branches** in your target Verilog repository:

### 1. **Baseline Branch** (`<problem_id>_baseline`)
- **Purpose:** Starting point for the agent
- **Contains:** Incomplete/broken code that needs fixing
- **Does NOT contain:** Hidden test files or the solution

### 2. **Test Branch** (`<problem_id>_test`)
- **Purpose:** Hidden test suite to validate the solution
- **Contains:** All test files that will verify the agent's fix
- **Does NOT contain:** The solution code

### 3. **Golden Branch** (`<problem_id>_golden`)
- **Purpose:** Reference solution for validation
- **Contains:** Correct implementation of the solution
- **Does NOT contain:** Hidden test files (tests are separate)

---

## Part 2: Creating a New Problem

### Step 1: Create Local Problem Repository

Create a new git repository for your problems with the correct HUD directory structure:

```bash
# Create problem repository
cd ~/Documents/GitHub
mkdir verilog-problems
cd verilog-problems

# Initialize git
git init
git config user.email "you@example.com"
git config user.name "Your Name"

# Create HUD-required structure
mkdir -p sources      # ✅ Verilog files go here (NOT rtl/)
mkdir -p tests        # ✅ Test files go here (NOT harness/)
mkdir -p docs         # Optional: specifications

# Create pyproject.toml
cat > pyproject.toml << 'EOF'
[project]
name = "verilog-problems"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "cocotb>=1.8.0",
    "pytest>=7.0.0",
    "pytest-xdist>=3.0.0",
]
EOF

# Create README
cat > README.md << 'EOF'
# Verilog Problems
Local repository for HUD verilog evaluation problems.
EOF

# Initial commit
git add .
git commit -m "Initial commit"
```

**CRITICAL:** Use `sources/` and `tests/`, NOT `rtl/` and `harness/`!

### Step 2: Create the Complete Solution Branch

Create a branch with EVERYTHING (solution + tests):

```bash
# Create complete solution branch
git checkout -b simple_adder

# Add your Verilog source files
cat > sources/simple_adder.sv << 'EOF'
module simple_adder (
    input wire clk,
    input wire [7:0] a,
    input wire [7:0] b,
    output reg [7:0] sum
);
    always @(posedge clk) begin
        sum <= a + b;  // Complete implementation
    end
endmodule
EOF
```

**Create hidden test WITH pytest wrapper (CRITICAL):**

```bash
cat > tests/test_simple_adder_hidden.py << 'EOF'
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

@cocotb.test()
async def test_addition(dut):
    """Test basic addition"""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    await RisingEdge(dut.clk)
    dut.a.value = 5
    dut.b.value = 3
    await RisingEdge(dut.clk)
    assert dut.sum.value == 8, f"Expected 8, got {dut.sum.value}"

# ✅ CRITICAL: Pytest wrapper function
def test_simple_adder_hidden_runner():
    import os
    from pathlib import Path
    from cocotb_tools.runner import get_runner
    
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    
    sources = [proj_path / "sources/simple_adder.sv"]  # Note: sources/ not rtl/
    
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="simple_adder",
        always=True,
    )
    runner.test(
        hdl_toplevel="simple_adder",
        test_module="test_simple_adder_hidden"
    )
EOF
```

**Add documentation (optional but recommended):**

```bash
cat > docs/Specification.md << 'EOF'
# Simple Adder Specification

## Interface
- `clk`: Clock input (rising edge triggered)
- `a[7:0]`: 8-bit first operand
- `b[7:0]`: 8-bit second operand
- `sum[7:0]`: 8-bit addition result

## Behavior
On each rising clock edge, compute: `sum = a + b`
EOF

cat > prompt.txt << 'EOF'
Implement an 8-bit synchronous adder in sources/simple_adder.sv.
See docs/Specification.md for details.
EOF
```

**CRITICAL: Verify golden solution passes tests:**

```bash
# Install dependencies
cd ~/Documents/GitHub/verilog-problems
uv pip install -e .

# Run tests - should PASS
pytest tests/test_simple_adder_hidden.py -v

# Expected output:
# test_addition PASSED
# test_simple_adder_hidden_runner PASSED
```

**Commit everything:**
```bash
git add .
git commit -m "Add simple_adder problem with complete solution and tests"
```

### Step 3: Create the Baseline Branch

Baseline = what the agent starts with (no solution, **NO TESTS AT ALL**):

**⚠️ CRITICAL: Remove ALL tests from baseline, not just hidden tests!**

```bash
# Create baseline branch from complete
git checkout -b simple_adder_baseline

# ❌ WRONG: Only removing hidden test
# rm tests/test_simple_adder_hidden.py

# ✅ CORRECT: Remove ENTIRE tests directory
rm -rf tests/

# Empty out the implementation (or introduce bugs)
cat > sources/simple_adder.sv << 'EOF'
module simple_adder (
    input wire clk,
    input wire [7:0] a,
    input wire [7:0] b,
    output reg [7:0] sum
);
    // TODO: Implement the adder logic
endmodule
EOF

# Commit
git add .
git commit -m "Baseline: Empty implementation, no tests directory"
```

**Why remove ALL tests?**

If you leave ANY test file (even a "public" one), and it references a hidden test module, the agent will see a `ModuleNotFoundError` and try to create that missing module, contaminating the solution!

### Step 4: Create the Test Branch

Test branch = baseline + hidden tests (for grading):

```bash
# Create test branch from baseline
git checkout -b simple_adder_test

# Restore ONLY the hidden test from complete branch
git checkout simple_adder -- tests/test_simple_adder_hidden.py

# Commit
git add tests/
git commit -m "Add hidden tests"
```

### Step 5: Create the Golden Branch

Golden branch = baseline + solution (**NO TESTS - solution code only**):

```bash
# Go back to baseline (which has no tests directory)
git checkout simple_adder_baseline

# Create golden branch (inherits no tests from baseline)
git checkout -b simple_adder_golden

# Restore ONLY the solution from complete branch
git checkout simple_adder -- sources/simple_adder.sv

# Verify no tests directory exists
ls -la tests/ 2>&1 && echo "❌ ERROR: Golden has tests!" || echo "✅ Correct: No tests"

# Commit
git add sources/
git commit -m "Golden solution - implementation only, no tests"
```

**Important:** Golden branch should ONLY contain the solution code. No test files at all! Since we created it from baseline (which has no tests), this is automatic.

### Step 6: Verify All Branches

```bash
# Show all branches
git branch

# Should show:
#   simple_adder (complete)
#   simple_adder_baseline
#   simple_adder_golden
#   simple_adder_test

# Quick verification
for branch in simple_adder_baseline simple_adder_test simple_adder_golden; do
    echo "========== $branch =========="
    git checkout $branch
    echo "Source files:"
    ls -lh sources/
    echo "Test files:"
    ls -lh tests/ 2>&1 || echo "No tests"
    echo ""
done
```

### Visual Summary of Branches
(Be mindful not to loose extra files and subdirectory structure inside source. The original context structure should not change)

```
simple_adder (complete - used for development only)
├── sources/simple_adder.sv (✓ complete)
└── tests/test_simple_adder_hidden.py (✓ present)

simple_adder_baseline (agent starts here)
├── sources/simple_adder.sv (✗ empty/broken)
└── (NO tests directory at all!) ⚠️ CRITICAL

simple_adder_test (for grading)
├── sources/simple_adder.sv (✗ empty/broken)
└── tests/
    ├── test_simple_adder.py (runner - optional)
    └── test_simple_adder_hidden.py (✓ hidden tests)

simple_adder_golden (reference solution)
├── sources/simple_adder.sv (✓ complete)
└── (NO tests directory at all!) ⚠️ CRITICAL
```

**⚠️ Key Point:** Only the `test` branch should have tests. Baseline and golden must have NO tests directory to prevent agent contamination!

---

## Part 3: Register the Problem in the Framework

### Step 1: Copy Local Repo to Framework Build Context

Since we're working locally, we need to copy our repository into the Docker build context:

```bash
# Navigate to framework
cd ~/Documents/GitHub/verilog-coding-template

# Create local-repos directory
mkdir -p local-repos

# Copy your problem repository
cp -r ~/Documents/GitHub/verilog-problems local-repos/problems

# Verify
ls -la local-repos/problems/
git -C local-repos/problems branch -a
```

### Step 2: Add Problem to Registry

Edit `src/hud_controller/problems/basic.py`:

```bash
cd ~/Documents/GitHub/verilog-coding-template
code src/hud_controller/problems/basic.py
# or: vim src/hud_controller/problems/basic.py
```

**Add your problem at the end:**

```python
PROBLEM_REGISTRY.append(
    ProblemSpec(
        id="simple_adder",  # Must match your branch prefix
        description="""Implement an 8-bit synchronous adder.

Task: Implement sources/simple_adder.sv

Interface:
- clk: Clock signal (rising edge triggered)
- a[7:0]: First 8-bit operand
- b[7:0]: Second 8-bit operand
- sum[7:0]: 8-bit addition result

Requirements:
On each rising clock edge, compute sum = a + b.
Addition is unsigned and wraps on overflow.

See docs/Specification.md for complete details.
""",
        difficulty="easy",  # "easy", "medium", or "hard"
        base="simple_adder_baseline",    # Must match branch name EXACTLY
        test="simple_adder_test",        # Must match branch name EXACTLY
        golden="simple_adder_golden",    # Must match branch name EXACTLY
        test_files=["tests/test_simple_adder_hidden.py"],  # Path in repo
        
        # Synthesis checking (REQUIRED for all problems)
        check_synthesis=True,                # Enable synthesis validation
        synth_top_module="simple_adder",     # Top-level module name
        synth_target="generic",              # Target: 'generic', 'ice40', 'ecp5'
    )
)
```

**Key Points:**
- `id`: Used for Docker image naming and CLI commands
- `description`: Full task prompt that the agent sees
- Branch names must EXACTLY match your git branches (case-sensitive!)
- `test_files`: Path relative to repo root
- `check_synthesis`: **REQUIRED** - Must be `True` for all problems
- `synth_top_module`: **REQUIRED** - The top-level Verilog module name

### Step 3: Update Dockerfile to Use Local Repo

Edit `Dockerfile` around line 108-111:

```bash
code Dockerfile
# or: vim Dockerfile
```

**Find these lines and update:**

```dockerfile
# Change this line (ALWAYS increment the number when changing repo!)
ENV random=random8  # ← Increment this!

# Change from git clone to COPY (for local repo)
# OLD: RUN git clone https://github.com/... /home/ubuntu/example-codebase
# NEW:
COPY --chown=ubuntu:ubuntu local-repos/problems /home/ubuntu/example-codebase

WORKDIR /home/ubuntu/example-codebase
```

**CRITICAL:** The `random` variable MUST be incremented every time you change the repository or Docker will use cached old version!

### Step 4: Verify Yosys is Installed (REQUIRED for Synthesis)

Since synthesis checking is REQUIRED, make sure `yosys` is installed in the Dockerfile. Check that the package list includes `yosys`:

```dockerfile
RUN apt-get update -y \
  && apt-get install -y --no-install-recommends \
  # ... other packages ...
  iverilog \
  verilator \
  yosys \
  # ... rest of packages ...
```

**If `yosys` is missing:** Add it to the package installation list. The Docker image must have `yosys` installed for synthesis checks to work.

---

## Part 4: Build and Validate

### Step 1: Build Docker Image

```bash
cd ~/Documents/GitHub/verilog-coding-template

# Build image for your specific problem
uv run utils/imagectl3.py verilog_ -b --ids simple_adder
```

**What this does:**
1. Builds a Docker image named `test_verilog_simple_adder`
2. Copies your local repository into the image
3. Checks out all three branches
4. Generates `test.patch` (baseline → test diff)
5. Generates `golden.patch` (baseline → golden diff)
6. Installs dependencies (cocotb, pytest, etc.)

**Expected output:**
```
INFO  Building image test_verilog_simple_adder
INFO  Copying local repository...
INFO  Checking out branches...
INFO  Generating patches...
INFO  ✓ Build succeeded for test_verilog_simple_adder
```

**Verify image exists:**
```bash
docker images | grep simple_adder
# Should show: test_verilog_simple_adder
```

### Step 2: Validate the Problem

**THIS IS THE MOST IMPORTANT STEP!**

```bash
# Validate your problem
uv run utils/imagectl3.py verilog_ -v --ids simple_adder
```

**What validation checks (7 total):**

1. **Baseline compiles** ✅
   - Empty/broken implementation is syntactically valid
   
2. **Test patch applies cleanly** ✅
   - No merge conflicts when adding tests
   
3. **Tests FAIL with baseline** ✅
   - Hidden tests fail because there's no implementation
   - **This proves the problem needs solving!**
   
4. **Golden patch applies cleanly** ✅
   - No merge conflicts when adding solution
   
5. **Golden compiles** ✅
   - Solution is syntactically correct
   
6. **Golden synthesizes** ✅
   - Solution passes Yosys synthesis
   - **This proves the problem is synthesizable for real hardware!**
   
7. **Tests PASS with golden** ✅
   - Solution actually works!
   - **This proves the problem is solvable!**

**Expected output:**
```
INFO  Validating test_verilog_simple_adder
INFO  Phase 1: Baseline compiles
✓ Baseline compiles successfully

INFO  Phase 2: Test patch applies and tests fail
✓ Test patch applies cleanly
✓ Tests fail as expected (no implementation)

INFO  Phase 3: Golden patch applies and tests pass
✓ Golden patch applies cleanly
✓ Golden compiles successfully
✓ Tests pass with golden solution
✓ Synthesis pass with golden solution

INFO  ✓ Validation successful for simple_adder
```

**If validation fails, see Troubleshooting section below.**

### Step 3: Generate JSON Configs (Optional)

```bash
# Generate JSON configs for HUD
uv run utils/imagectl3.py verilog_ -j

# This creates/updates local-hud.json
```

**Only needed if you want to run AI agents on your task.**

**Note:** When running evaluations, if `check_synthesis=True` is set in your problem spec, the agent's solution will be checked for synthesizability during grading. 

**Important Grading Behavior:**
- **Simulation (tests) runs first** - The agent's solution is tested via simulation
- **Synthesis only runs if simulation passes** - If simulation fails, synthesis is skipped entirely
- **Both must pass for success** - Both simulation AND synthesis must pass for a successful grade (0% if either fails)

---

## Part 4.5: Synthesis Checking (REQUIRED)

**⚠️ REQUIRED:** All problems MUST have synthesis checking enabled. This ensures your RTL is not just simulatable but also synthesizable for real FPGAs/ASICs!

### Why Synthesis Checking?

Synthesis checking verifies that:
- ✅ Your RTL uses only synthesizable constructs
- ✅ Design can be converted to gates/LUTs for hardware
- ✅ No simulation-only constructs (like delays, initial blocks in some contexts)
- ✅ Design meets basic timing/resource requirements


### How to Enable Synthesis Checking

Edit your problem in `src/hud_controller/problems/basic.py` and add synthesis parameters:

```python
PROBLEM_REGISTRY.append(
    ProblemSpec(
        id="your_problem",
        description="...",
        difficulty="medium",
        base="your_problem_baseline",
        test="your_problem_test",
        golden="your_problem_golden",
        test_files=["tests/test_your_problem_hidden.py"],
        
        # Enable synthesis checking
        check_synthesis=True,                    # Enable synthesis
        synth_top_module="your_top_module",     # Top-level module name
        synth_target="generic",                  # Target: 'generic', 'ice40', 'ecp5'
        synth_sources=[],                        # Optional: specific files (auto-discovers if empty)
    )
)
```

### Synthesis Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_synthesis` | bool | `False` | Enable/disable synthesis checking |
| `synth_top_module` | str | `None` | **Required if enabled**: Top-level module name |
| `synth_target` | str | `"generic"` | Synthesis target (see table below) |
| `synth_sources` | list[str] | `[]` | Specific source files (empty = auto-discover all `.v`/`.sv` in `sources/`) |

### Supported Synthesis Targets

| Target | Description | Use Case |
|--------|-------------|----------|
| `generic` | Generic ASIC/FPGA synthesis | Default, works for most designs |
| `ice40` | Lattice iCE40 FPGA | For iCE40-specific designs |
| `ecp5` | Lattice ECP5 FPGA | For ECP5-specific designs |
| `gowin` | Gowin FPGAs | For Gowin-specific designs |

**Most problems should use `"generic"`** unless targeting a specific FPGA family.

### Example: RC5 with Synthesis

```python
PROBLEM_REGISTRY.append(
    ProblemSpec(
        id="rc5_ca_keygen",
        description="Implement RC5 encryption with CA key generation...",
        difficulty="hard",
        base="rc5_ca_keygen_baseline",
        test="rc5_ca_keygen_test",
        golden="rc5_ca_keygen_golden",
        test_files=["tests/test_rc5_ca_keygen_hidden.py"],
        
        # Synthesis checking enabled
        check_synthesis=True,
        synth_top_module="rc5_enc_16bit",  # Top module
        synth_target="generic",             # Generic synthesis
    )
)
```

### What Happens During Synthesis Check?

When you run validation with synthesis enabled:

```bash
uv run utils/imagectl3.py verilog_ -bv --ids your_problem
```

The validation now includes **7 checks** (instead of 6):

1. ✅ Baseline compiles
2. ✅ Test patch applies
3. ✅ Tests fail with baseline
4. ✅ Golden patch applies
5. ✅ Golden compiles
6. **✅ Golden synthesizes** ← NEW!
7. ✅ Tests pass with golden

If synthesis fails, you'll see errors like:
```
ERROR: Synthesis check failed: 
ERROR: Yosys synthesis error at line 42 in sources/module.v:
    Combinational loop detected
```

### Testing Synthesis Manually

You can also test synthesis manually in the Docker container:

```bash
# Start container
docker run -it --rm verilog_your_problem bash

# Inside container, apply patches
cd /home/ubuntu/example-verilog-codebase
git apply /home/root/golden.patch

# Run Yosys synthesis
cd sources
yosys -p "read_verilog -sv *.sv; synth -top your_module; stat"

# Check for errors
echo $?  # Should be 0 for success
```

### Common Synthesis Issues and Fixes

#### Issue: "Latch inferred"
```
ERROR: Latch inferred for signal 'counter'
```
**Fix:** Ensure all outputs are assigned in all branches:
```systemverilog
// ❌ BAD: Latch (counter not assigned when enable=0)
always @(posedge clk) begin
    if (enable)
        counter <= counter + 1;
end

// ✅ GOOD: No latch
always @(posedge clk) begin
    if (enable)
        counter <= counter + 1;
    else
        counter <= counter;  // Explicit assignment
end
```

#### Issue: "Combinational loop"
```
ERROR: Combinational loop detected
```
**Fix:** Break feedback loops with registers:
```systemverilog
// ❌ BAD: Combinational loop
assign out = in ^ out;

// ✅ GOOD: Register breaks loop
always @(posedge clk)
    out <= in ^ out;
```

#### Issue: "initial blocks not synthesizable"
```
ERROR: initial blocks are not synthesizable
```
**Fix:** Use reset instead of initial:
```systemverilog
// ❌ BAD: initial block
initial begin
    counter = 0;
end

// ✅ GOOD: Reset signal
always @(posedge clk or negedge reset_n) begin
    if (!reset_n)
        counter <= 0;
end
```

### Best Practices

1. **Test synthesis early** - Enable it from the start, not as an afterthought
2. **Keep designs simple** - Avoid complex nested conditionals
3. **Use standard constructs** - Stick to well-known synthesizable patterns
4. **Check golden first** - Make sure your golden solution synthesizes before validating
5. **Read the errors** - Yosys provides helpful error messages

### When Synthesis Check Fails

If validation fails at synthesis:
```
[validate verilog_problem]  ERROR    Synthesis check failed: Combinational loop detected
❌ testGoldenSynthesisCheck FAILED
```

**Steps to fix:**
1. Run synthesis manually (see above) to get full error log
2. Fix the synthesis errors in your golden solution
3. Update the golden branch in your repo
4. Increment `random` in Dockerfile
5. Rebuild and validate again

---

## Part 5: Test With an Agent (Optional)

**NOTE:** This step requires API keys and costs money (~$3-5 per run). Only do this if you want to measure task difficulty.

### Generate JSON Config First

```bash
cd ~/Documents/GitHub/verilog-coding-template

# Generate local-hud.json
uv run utils/imagectl3.py verilog_ -j
```

### Run AI Agent Locally

**⚠️ Important:** Always use `uv run hud eval` (not just `hud eval`). This ensures you're using the project's dependencies and avoids version conflicts.

```bash
# ============================================
# OPTION 1: Run with Claude Opus 4.5
# ============================================
# Requires ANTHROPIC_API_KEY - PLEASE CHECK WITH USER IF THEY GOT THE API KEY FROM SONYA

# Run with Claude Opus 4.5 (all problems):
uv run hud eval local-claude-hud.json claude \
  --model claude-opus-4-5 \
  --max-steps 50 \
  --group-size 5 \
  --yes

# To run just ONE specific problem (faster for testing):
# First, create a filtered JSON file with just your problem
python3 -c "
import json
with open('local-claude-hud.json', 'r') as f:
    data = json.load(f)
problem = [item for item in data if item['id'] == 'YOUR_PROBLEM_ID']
with open('local-claude-hud-single.json', 'w') as f:
    json.dump(problem, f, indent=2)
"

# Then run on just that problem
uv run hud eval local-claude-hud-single.json claude \
  --model claude-opus-4-5 \
  --max-steps 50 \
  --group-size 5 \
  --yes

# ============================================
# OPTION 2: Run with gpt-5.2-codex (OpenAI)
# ============================================
# Requires OPENAI_API_KEY - Get from https://platform.openai.com

# Run with gpt-5.2-codex (all problems):
uv run hud eval local-openai-hud.json openai \
  --model gpt-5.2-codex \
  --max-steps 50 \
  --group-size 5 \
  --yes

# To run just ONE specific problem (faster for testing):
# First, create a filtered JSON file with just your problem
python3 -c "
import json
with open('local-openai-hud.json', 'r') as f:
    data = json.load(f)
problem = [item for item in data if item['id'] == 'YOUR_PROBLEM_ID']
with open('local-openai-hud-single.json', 'w') as f:
    json.dump(problem, f, indent=2)
"

# Then run on just that problem
uv run hud eval local-openai-hud-single.json openai \
  --model gpt-5.2-codex \
  --max-steps 50 \
  --group-size 5 \
  --yes

# ============================================
# OPTION 3: Run with Gemini (Google)
# ============================================
# Requires GEMINI_API_KEY - Get from https://aistudio.google.com/app/apikey

# Run with Gemini (all problems):
uv run hud eval local-gemini-hud.json gemini \
  --model gemini-2.5-pro \
  --max-steps 50 \
  --group-size 5 \
  --yes

# To run just ONE specific problem (faster for testing):
# First, create a filtered JSON file with just your problem
python3 -c "
import json
with open('local-gemini-hud.json', 'r') as f:
    data = json.load(f)
problem = [item for item in data if item['id'] == 'YOUR_PROBLEM_ID']
with open('local-gemini-hud-single.json', 'w') as f:
    json.dump(problem, f, indent=2)
"

# Then run on just that problem
uv run hud eval local-gemini-hud-single.json gemini \
  --model gemini-2.5-pro \
  --max-steps 50 \
  --group-size 5 \
  --yes
```

**What this does:**
- Starts a Docker container with your problem
- Gives the AI agent access to the baseline code
- Agent can read files, write code, run tests
- After N steps, applies hidden tests to grade the solution
- **Grading process:**
  - **Simulation (tests) runs first** - Tests the agent's solution via simulation
  - **Synthesis only runs if simulation passes** - If simulation fails, synthesis is skipped
  - **Both must pass for success** - Both simulation AND synthesis must pass for a successful grade (0% if either fails)
- Shows success/failure and logs all agent actions

**Note on providers:**
- **Claude** uses `bash` and `str_replace_based_edit_tool` tools
- **gpt-5.2-codex** uses `bash` and `str_replace_based_edit_tool` tools (configured to use `bash` instead of `shell` which gpt-5.2-codex doesn't support)
- **Gemini** uses `bash` and `str_replace_based_edit_tool` tools
- All agents have the same capabilities - the framework automatically configures the correct tools for each provider

**You'll see output like:**
```
Starting evaluation for simple_adder...
Agent: Reading prompt.txt...
Agent: Examining sources/simple_adder.sv...
Agent: Writing implementation...
Agent: Running tests...
...
✓ Agent solved the problem in 15 steps!
```

### For Multiple Problems (Parallel Evaluation)

```bash
# Run all problems with 4 parallel workers (Claude)
uv run hud eval local-claude-hud.json claude \
  --model claude-opus-4-5 \
  --max-steps 50 \
  --group-size 5 \
  --max-concurrent 4 \
  --yes

# Run all problems with 4 parallel workers (gpt-5.2-codex)
uv run hud eval local-openai-hud.json openai \
  --model gpt-5.2-codex \
  --max-steps 50 \
  --group-size 5 \
  --max-concurrent 4 \
  --yes

# Run all problems with 4 parallel workers (Gemini)
uv run hud eval local-gemini-hud.json gemini \
  --model gemini-2.5-pro \
  --max-steps 50 \
  --group-size 5 \
  --max-concurrent 4 \
  --yes
```

---

## Common Issues and Troubleshooting

**REMINDER:** If stuck for more than 15 minutes, email sonya@phinity.ai!

### Issue 1: "collected 0 items" - Pytest Can't Find Tests

**Symptom:**
```
============================= test session starts ==============================
collected 0 items
============================ no tests ran in 0.04s =============================
```

**Cause:** Missing pytest wrapper function in your test file.

**Solution:** Add pytest wrapper at end of test file:

```python
def test_simple_adder_hidden_runner():
    import os
    from pathlib import Path
    from cocotb_tools.runner import get_runner
    
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    
    sources = [proj_path / "sources/simple_adder.sv"]  # sources/ not rtl/!
    
    runner = get_runner(sim)
    runner.build(sources=sources, hdl_toplevel="simple_adder", always=True)
    runner.test(hdl_toplevel="simple_adder", test_module="test_simple_adder_hidden")
```

### Issue 2: "No such file: rtl/module.sv"

**Symptom:**
```
error: Unable to find the root module "module" in the Verilog source.
```

**Cause:** Using `rtl/` directory instead of `sources/`.

**Solution:**
1. Use `sources/` directory, not `rtl/`
2. Update pytest wrapper:
   ```python
   sources = [proj_path / "sources/module.sv"]  # NOT rtl/
   ```

### Issue 3: Tests Pass with Baseline (Should Fail!)

**Symptom:** Validation says "Test patch did not cause tests to fail"

**Causes:**
- Baseline isn't actually broken (still has working implementation)
- Tests are too lenient

**Solution:**
1. Verify baseline has empty/broken implementation
2. Test manually:
   ```bash
   git checkout simple_adder_baseline
   pytest tests/test_simple_adder_hidden.py -v  # Should FAIL
   ```

### Issue 4: Tests Fail with Golden (Should Pass!)

**Symptom:** "Golden patch did not fix tests"

**Causes:**
- Golden solution has bugs
- Test expected values don't match golden outputs
- Missing source files in pytest wrapper

**Solution:**
1. Test golden manually:
   ```bash
   git checkout simple_adder_golden
   # Manually add test file
   git checkout simple_adder -- tests/test_simple_adder_hidden.py
   pytest tests/test_simple_adder_hidden.py -v  # Should PASS
   ```
2. For multi-file projects, list ALL files:
   ```python
   sources = [
       proj_path / "sources/module1.sv",
       proj_path / "sources/module2.sv",
   ]
   ```

### Issue 5: Docker Not Seeing Latest Changes

**Symptom:** Built image uses old code

**Solution:** Increment `random` in Dockerfile:

```dockerfile
ENV random=random9  # ← Change this number!
```

Docker caches the repository copy. Changing this breaks the cache.

### Issue 6: Branch Name Mismatch

**Symptom:** "Branch not found" during build

**Solution:** Branch names in `basic.py` must EXACTLY match git branches (case-sensitive):

```bash
# Check your actual branches
cd ~/Documents/GitHub/verilog-problems
git branch

# Compare with basic.py
# If branch is "simple_adder_baseline", then:
base="simple_adder_baseline",  # Must match exactly!
```

---

## Checklist: Adding a New Problem

Use this checklist to ensure you haven't missed any steps:

### Prerequisites:
- [ ] Cloned verilog-coding-template framework
- [ ] Ran `uv sync` to install dependencies
- [ ] Docker is installed and running

### In Your Problem Repository:
- [ ] Created repository with `sources/` and `tests/` directories (NOT `rtl/` and `harness/`)
- [ ] Created complete solution branch with working implementation
- [ ] Created hidden test file with pytest wrapper function
- [ ] Verified golden solution passes all tests locally
- [ ] Created `<problem>_baseline` branch (empty code, **NO tests directory at all**)
- [ ] Created `<problem>_test` branch (empty code + all test files)
- [ ] Created `<problem>_golden` branch (complete code, **NO tests directory at all**)
- [ ] Verified all three branches exist: `git branch`
- [ ] **⚠️ VERIFIED baseline has NO tests: `git checkout <problem>_baseline && ls tests/ 2>&1 | grep "No such file"`**
- [ ] **⚠️ VERIFIED golden has NO tests: `git checkout <problem>_golden && ls tests/ 2>&1 | grep "No such file"`**

### In Framework Repository:
- [ ] Copied problem repo to `local-repos/problems/`
- [ ] Added problem to `src/hud_controller/problems/basic.py`
- [ ] **⚠️ Enabled synthesis checking: `check_synthesis=True`**
- [ ] **⚠️ Set correct top module: `synth_top_module="your_module"`**
- [ ] Updated Dockerfile to use COPY instead of git clone
- [ ] **⚠️ Verified `yosys` is installed in Dockerfile (required for synthesis)**
- [ ] Incremented `random` variable in Dockerfile
- [ ] Branch names in `basic.py` EXACTLY match git branches

### Build & Validation:
- [ ] Built image: `uv run utils/imagectl3.py verilog_ -b --ids <problem_id>`
- [ ] Build succeeded without errors
- [ ] Validated: `uv run utils/imagectl3.py verilog_ -v --ids <problem_id>`
- [ ] ✅ Baseline compiles
- [ ] ✅ Test patch applies and tests FAIL
- [ ] ✅ Golden patch applies and tests PASS
- [ ] ✅ **Golden synthesizes successfully**
- [ ] All 7 validation checks passed

### Optional (if running agents):
- [ ] Generated JSON: `uv run utils/imagectl3.py verilog_ -j`
- [ ] Set API keys:
  - Claude: `hud set ANTHROPIC_API_KEY sk-ant-your-key-here` or `$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"` (PowerShell)
  - GPT: `hud set OPENAI_API_KEY sk-your-key-here` or `$env:OPENAI_API_KEY="sk-your-key-here"` (PowerShell)
- [ ] Tested with Claude agent: `uv run hud eval local-claude-hud-single.json claude --model claude-opus-4-5 --max-steps 50 --group-size 5 --yes`
- [ ] Tested with GPT agent: `uv run hud eval local-openai-hud-single.json openai --model gpt-5.2-codex --max-steps 50 --group-size 5 --yes`

---

## Quick Reference Commands

```bash
# Build specific problem
uv run utils/imagectl3.py verilog_ -b --ids PROBLEM_ID

# Validate specific problem
uv run utils/imagectl3.py verilog_ -v --ids PROBLEM_ID

# Build + validate + generate JSON
uv run utils/imagectl3.py verilog_ -bvj --ids PROBLEM_ID

# Generate JSON only
uv run utils/imagectl3.py verilog_ -j

# Run agent evaluation (requires API key)
# For all problems with Claude:
uv run hud eval local-claude-hud.json claude \
  --model claude-opus-4-5 \
  --max-steps 50 \
  --group-size 5 \
  --yes

# For all problems with gpt-5.2-codex:
uv run hud eval local-openai-hud.json openai \
  --model gpt-5.2-codex \
  --max-steps 50 \
  --group-size 5 \
  --yes

# For just ONE problem (recommended for testing):
# Create filtered JSON first (Claude):
python3 -c "import json; data=json.load(open('local-claude-hud.json')); json.dump([x for x in data if x['id']=='PROBLEM_ID'], open('test-claude.json','w'), indent=2)"
# Then run on it:
uv run hud eval test-claude.json claude \
  --model claude-opus-4-5 \
  --max-steps 50 \
  --group-size 5 \
  --yes

# Create filtered JSON first (GPT):
python3 -c "import json; data=json.load(open('local-openai-hud.json')); json.dump([x for x in data if x['id']=='PROBLEM_ID'], open('test-openai.json','w'), indent=2)"
# Then run on it:
uv run hud eval test-openai.json openai \
  --model gpt-5.2-codex \
  --max-steps 50 \
  --group-size 5 \
  --yes
```

---

## Common Issues & Troubleshooting

### Issue 1: Agent Creates Hidden Test File (MOST COMMON!)

**Symptom:** Agent creates `test_<module>_hidden.py` that should have been provided by grading infrastructure.

**Root Cause:** Baseline or golden branch contains a test file that references the hidden test module, causing `ModuleNotFoundError`.

**How to Diagnose:**
```bash
# Check if baseline has ANY tests (it should NOT!)
git checkout <problem>_baseline
ls -la tests/  # Should fail with "No such file or directory"

# Check if golden has ANY tests (it should NOT!)
git checkout <problem>_golden
ls -la tests/  # Should fail with "No such file or directory"

# Only test branch should have tests
git checkout <problem>_test
ls -la tests/  # Should show test files
```

**Fix:**
```bash
# Remove ALL tests from baseline
git checkout <problem>_baseline
git rm -rf tests/
git commit -m "Fix: Remove all tests from baseline"
git push origin <problem>_baseline --force

# Remove ALL tests from golden
git checkout <problem>_golden
git rm -rf tests/
git commit -m "Fix: Remove all tests from golden"
git push origin <problem>_golden --force

# Rebuild and validate
cd /path/to/verilog-template
uv run utils/imagectl3.py verilog_ -bv --ids <problem_id>
```

**Prevention:**
- Always use `rm -rf tests/` when creating baseline, not `rm tests/test_*_hidden.py`
- Never include ANY test files in baseline or golden branches
- Check RC5 problem as reference for correct structure

---

## Debugging Tips

**Check what's in Docker image:**
```bash
docker run --rm test_verilog_<problem_id> bash -c "
cd /home/ubuntu/example-codebase &&
git branch -a &&
ls -R sources/ tests/
"
```

**Check patches were generated:**
```bash
docker run --rm test_verilog_<problem_id> bash -c "
ls -la /home/root/*.patch &&
head -20 /home/root/test.patch
"
```

**Run tests manually in container:**
```bash
docker run --rm -it test_verilog_<problem_id> bash
cd /home/ubuntu/example-codebase
git apply /home/root/test.patch
uv run pytest tests/ -v -s
```

---

## Example: Simple Counter (for reference)

This is a brief reference showing the structure of the `simple_counter` example problem:

**Baseline branch:** Empty implementation, no hidden tests
```
sources/simple_counter.sv      ← Empty module
tests/test_simple_counter.py   ← Public test (optional)
```

**Test branch:** Adds hidden tests to baseline
```
sources/simple_counter.sv           ← Still empty
tests/test_simple_counter_hidden.py ← ADDED
```

**Golden branch:** Adds solution to baseline (no tests)
```
sources/simple_counter.sv      ← COMPLETE implementation
```

**Key files:**
- `sources/simple_counter.sv` - The Verilog module (empty in baseline, complete in golden)
- `tests/test_simple_counter_hidden.py` - Hidden tests (only in test branch)
- Both test files have pytest wrapper functions

See the verilog-problems repository for full file contents.


---

## Support

**Stuck for more than 15 minutes?** Email sonya@phinity.ai

**Don't debug HUD setup issues on your own** - we'd rather help you quickly so you can focus on creating great problems!

---

**Last Updated:** November 2025  
**Framework Version:** 1.0
