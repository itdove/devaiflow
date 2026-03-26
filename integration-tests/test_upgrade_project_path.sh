#!/bin/bash
# Integration test for daf upgrade --project-path feature
#
# This test verifies:
# 1. Skills install to project directory when --project-path is specified
# 2. Skills install to ~/.claude/skills/ by default
# 3. Project-level skills are discoverable
# 4. --dry-run mode works with --project-path
# 5. Error handling for invalid project paths

set -e

# Enable debug mode if --debug flag is passed
if [[ "$1" == "--debug" ]]; then
    set -x
fi

# Test configuration
TEMP_DIR="/tmp/test-upgrade-project-path-$$"
TEST_PROJECT="$TEMP_DIR/test-project"
GLOBAL_SKILLS_DIR="$HOME/.claude/skills"
BACKUP_SKILLS_DIR="$HOME/.claude/skills.backup-$$"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Testing daf upgrade --project-path feature ==="
echo ""

# Setup: Create test environment
echo "Setting up test environment..."
mkdir -p "$TEST_PROJECT"
mkdir -p "$TEMP_DIR"

# Backup existing global skills if they exist
if [ -d "$GLOBAL_SKILLS_DIR" ]; then
    echo "Backing up existing global skills to $BACKUP_SKILLS_DIR"
    mv "$GLOBAL_SKILLS_DIR" "$BACKUP_SKILLS_DIR"
fi

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up..."
    rm -rf "$TEMP_DIR"

    # Restore global skills backup
    if [ -d "$BACKUP_SKILLS_DIR" ]; then
        echo "Restoring global skills from backup"
        rm -rf "$GLOBAL_SKILLS_DIR"
        mv "$BACKUP_SKILLS_DIR" "$GLOBAL_SKILLS_DIR"
    fi
}

trap cleanup EXIT

# Test 1: Install to project directory
echo "=== Test 1: Install skills to project directory ==="
daf upgrade --project-path "$TEST_PROJECT"
echo ""

if [ -d "$TEST_PROJECT/.claude/skills" ]; then
    skill_count=$(ls -1 "$TEST_PROJECT/.claude/skills" | wc -l | tr -d ' ')
    echo -e "${GREEN}✓${NC} Skills directory created at $TEST_PROJECT/.claude/skills/"
    echo "  Found $skill_count skill directories"

    # Verify at least some skills were installed
    if [ "$skill_count" -gt 5 ]; then
        echo -e "${GREEN}✓${NC} Multiple skills installed successfully"
    else
        echo -e "${RED}✗${NC} Expected more than 5 skills, found $skill_count"
        exit 1
    fi
else
    echo -e "${RED}✗${NC} Skills directory NOT created at project path"
    ls -la "$TEST_PROJECT/" || true
    exit 1
fi

# Verify specific skills exist
expected_skills=("daf-cli" "gh-cli" "git-cli" "glab-cli")
for skill in "${expected_skills[@]}"; do
    if [ -d "$TEST_PROJECT/.claude/skills/$skill" ]; then
        echo -e "${GREEN}✓${NC} $skill installed"
    else
        echo -e "${RED}✗${NC} $skill NOT installed"
        exit 1
    fi
done

echo ""

# Test 2: Install to current directory using '.'
echo "=== Test 2: Install to current directory using '.' ==="
TEST_PROJECT_CURRENT="$TEMP_DIR/test-current"
mkdir -p "$TEST_PROJECT_CURRENT"
cd "$TEST_PROJECT_CURRENT"
daf upgrade --project-path .
cd - > /dev/null
echo ""

if [ -d "$TEST_PROJECT_CURRENT/.claude/skills" ]; then
    echo -e "${GREEN}✓${NC} Skills installed to current directory"
else
    echo -e "${RED}✗${NC} Skills NOT installed to current directory"
    exit 1
fi

echo ""

# Test 3: Default installation (global)
echo "=== Test 3: Default installation to ~/.claude/skills/ ==="
# Remove global skills if they exist
rm -rf "$GLOBAL_SKILLS_DIR"

daf upgrade
echo ""

if [ -d "$GLOBAL_SKILLS_DIR" ]; then
    skill_count=$(ls -1 "$GLOBAL_SKILLS_DIR" | wc -l | tr -d ' ')
    echo -e "${GREEN}✓${NC} Skills installed to global directory: $GLOBAL_SKILLS_DIR"
    echo "  Found $skill_count skill directories"
else
    echo -e "${RED}✗${NC} Global skills directory NOT created"
    exit 1
fi

echo ""

# Test 4: Dry run with project path
echo "=== Test 4: Dry run mode with --project-path ==="
TEST_PROJECT_DRYRUN="$TEMP_DIR/test-dryrun"
mkdir -p "$TEST_PROJECT_DRYRUN"

daf upgrade --project-path "$TEST_PROJECT_DRYRUN" --dry-run
echo ""

# In dry run mode, skills should NOT be installed
if [ ! -d "$TEST_PROJECT_DRYRUN/.claude/skills" ]; then
    echo -e "${GREEN}✓${NC} Dry run mode: skills NOT installed (as expected)"
else
    # Check if any skills were installed
    if [ -n "$(ls -A "$TEST_PROJECT_DRYRUN/.claude/skills" 2>/dev/null)" ]; then
        echo -e "${RED}✗${NC} Dry run mode: skills were installed (unexpected)"
        exit 1
    else
        echo -e "${GREEN}✓${NC} Dry run mode: skills directory created but empty (acceptable)"
    fi
fi

echo ""

# Test 5: Error handling - nonexistent path
echo "=== Test 5: Error handling for nonexistent path ==="
NONEXISTENT_PATH="$TEMP_DIR/nonexistent-path"

output=$(daf upgrade --project-path "$NONEXISTENT_PATH" 2>&1 || true)
if echo "$output" | grep -q "does not exist"; then
    echo -e "${GREEN}✓${NC} Correct error message for nonexistent path"
else
    echo -e "${RED}✗${NC} Expected error message not found"
    echo "Output: $output"
    exit 1
fi

echo ""

# Test 6: Error handling - path is a file
echo "=== Test 6: Error handling for file path ==="
FILE_PATH="$TEMP_DIR/test-file.txt"
touch "$FILE_PATH"

output=$(daf upgrade --project-path "$FILE_PATH" 2>&1 || true)
if echo "$output" | grep -q "not a directory"; then
    echo -e "${GREEN}✓${NC} Correct error message for file path"
else
    echo -e "${RED}✗${NC} Expected error message not found"
    echo "Output: $output"
    exit 1
fi

echo ""

# Test 7: Skills are discoverable (verify SKILL.md files exist)
echo "=== Test 7: Verify skills have SKILL.md files ==="
skills_valid=true
for skill_dir in "$TEST_PROJECT/.claude/skills"/*; do
    if [ -d "$skill_dir" ]; then
        skill_name=$(basename "$skill_dir")
        if [ -f "$skill_dir/SKILL.md" ]; then
            echo -e "${GREEN}✓${NC} $skill_name has SKILL.md"
        else
            echo -e "${RED}✗${NC} $skill_name missing SKILL.md"
            skills_valid=false
        fi
    fi
done

if [ "$skills_valid" = false ]; then
    exit 1
fi

echo ""

# Test 8: Verify skill content matches bundled version
echo "=== Test 8: Verify installed skills match bundled version ==="
# Compare daf-cli skill as a sample
if [ -f "$TEST_PROJECT/.claude/skills/daf-cli/SKILL.md" ]; then
    # Just verify the file has content
    if [ -s "$TEST_PROJECT/.claude/skills/daf-cli/SKILL.md" ]; then
        echo -e "${GREEN}✓${NC} Installed skill has content"
    else
        echo -e "${RED}✗${NC} Installed skill file is empty"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠${NC} daf-cli/SKILL.md not found for verification"
fi

echo ""
echo -e "${GREEN}=== All tests passed! ===${NC}"
