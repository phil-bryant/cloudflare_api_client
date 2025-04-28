#!/bin/bash

# #authored-by-ai #claude-3.7-sonnet-thinking 
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

# Prerequisites:
#   - GitHub CLI (gh) installed and authenticated (https://cli.github.com/)
#   - Git installed and configured
#   - For --work option: WORK_GITHUB environment variable set or defined in ~/.env file
#     (format: WORK_GITHUB=your-org-name)
#   - Platform: 
#     * Designed for macOS
#     * Compatible with Linux (note: uses ~/.Trash for backups, not ~/.local/share/Trash)
#     * Not directly compatible with Windows (requires WSL, Git Bash, or similar)

# Accepts:
#   --private or --public       (mandatory visibility choice)
#   --work or --personal        (mandatory ownership choice)
#   --remove-existing           (optional - remove existing git repo and GitHub repo if they exist)
#
# Examples:
#   $0 --personal --private                    # private personal repo
#   $0 --work --public                         # public repo in work org
#   $0 --personal --private --remove-existing  # recreate even if exists

# Display usage information
show_usage() {
    echo "Usage: $0 --work|--personal --private|--public [--remove-existing]"
    echo ""
    echo "Required arguments:"
    echo "  --private or --public     Specify repository visibility"
    echo "  --work or --personal      Specify repository ownership (work org or personal account)"
    echo ""
    echo "Optional arguments:"
    echo "  --remove-existing         Remove existing git and GitHub repositories if they exist"
    echo ""
    echo "Examples:"
    echo "  $0 --personal --private                    # private personal repo"
    echo "  $0 --work --public                         # public repo in work org"
    echo "  $0 --personal --private --remove-existing  # recreate even if exists"
    exit 1
}

# --- Argument parsing ---
VISIBILITY=""
OWNER_TYPE=""
REMOVE_EXISTING=false

for arg in "$@"; do
    case "$arg" in
        --private|--public)
            VISIBILITY=${arg#--}
            ;;
        --work)
            OWNER_TYPE="work"
            ;;
        --personal)
            OWNER_TYPE="personal"
            ;;
        --remove-existing)
            REMOVE_EXISTING=true
            ;;
        *)
            echo "Error: Unknown argument '$arg'"
            show_usage
            ;;
    esac
done

# Ensure required args were provided
if [ -z "$VISIBILITY" ]; then
    echo "Error: Missing required argument --private or --public"
    show_usage
fi

if [ -z "$OWNER_TYPE" ]; then
    echo "Error: Missing required argument --work or --personal"
    show_usage
fi

# Get repository name from current directory
REPO_NAME=$(basename "$PWD")

# Configure repo specification
if [ "$OWNER_TYPE" = "work" ]; then
    # For organization, use org-name/repo-name format
    # First check if WORK_GITHUB is already in environment
    if [ -z "$WORK_GITHUB" ]; then
        # If not in environment, try to read from ~/.env
        if [ -f ~/.env ]; then
            WORK_GITHUB=$(grep WORK_GITHUB ~/.env | cut -d= -f2)
        fi
        
        # Check if we found a value
        if [ -z "$WORK_GITHUB" ]; then
            echo "ERROR: WORK_GITHUB environment variable not set and not found in ~/.env"
            echo "Please set the WORK_GITHUB environment variable or add it to ~/.env"
            echo "Format: WORK_GITHUB=your-org-name"
            exit 1
        fi
    fi
    
    REPO_SPEC="$WORK_GITHUB/$REPO_NAME"
    REPO_URL="git@github.com:$WORK_GITHUB/$REPO_NAME.git"
else
    # For personal repos, just use repo name
    REPO_SPEC="$REPO_NAME"
    GITHUB_USERNAME=$(gh api user | grep login | cut -d'"' -f4)
    REPO_URL="git@github.com:$GITHUB_USERNAME/$REPO_NAME.git"
fi

# Check for existing .git directory
if [ -d .git ]; then
    if [ "$REMOVE_EXISTING" = true ]; then
        echo "Moving existing .git directory to ~/.Trash/.git-$REPO_NAME-$(date +%s)"
        mkdir -p ~/.Trash
        mv .git ~/.Trash/.git-$REPO_NAME-$(date +%s)
        echo "Existing .git directory moved to trash"
    else
        echo "Error: This directory already has a .git repository."
        echo "Use --remove-existing if you want to remove it and create a new repository."
        show_usage
    fi
fi

# Check if GitHub repository already exists
if gh repo view "$REPO_SPEC" &>/dev/null; then
    if [ "$REMOVE_EXISTING" = true ]; then
        echo "Attempting to delete existing GitHub repository: $REPO_SPEC"
        
        # Try to delete repository, with permission check
        if ! gh repo delete "$REPO_SPEC" --yes 2>/tmp/gh_delete_error; then
            echo "ERROR: Cannot delete the GitHub repository."
            echo "You may need admin rights or the delete_repo scope."
            echo "You can request it with: gh auth refresh -h github.com -s delete_repo"
            cat /tmp/gh_delete_error
            echo "Aborting operation."
            exit 1
        else
            echo "Existing GitHub repository deleted successfully"
            # Add a small delay to allow GitHub to process the deletion
            sleep 2
        fi
    else
        echo "Error: GitHub repository $REPO_SPEC already exists."
        echo "Use --remove-existing if you want to delete it and create a new repository."
        show_usage
    fi
fi

# Initialize git
git init -b main
git add .
git commit -m "Initial commit"

# Create repository on GitHub
echo "Creating repository $REPO_SPEC with $VISIBILITY visibility..."

# First create the repository without setting the remote or pushing
if ! gh repo create "$REPO_SPEC" --"$VISIBILITY" --source=. --push=false 2>/tmp/gh_create_error; then
    # Check if error is that repo already exists but we should continue
    if grep -q "Name already exists" /tmp/gh_create_error && [ "$REMOVE_EXISTING" = true ]; then
        echo "Repository already exists but --remove-existing was specified."
        echo "Attempting to connect to the existing repository..."
    else
        echo "Failed to create repository:"
        cat /tmp/gh_create_error
        exit 1
    fi
fi

# Now set the remote with SSH URL
echo "Setting up remote with SSH URL: $REPO_URL"
if git remote get-url origin &>/dev/null; then
    # Remote exists, update it
    git remote set-url origin "$REPO_URL"
else
    # Remote doesn't exist, add it
    git remote add origin "$REPO_URL"
fi

# Push to the remote
if ! git push -u origin main; then
    echo "ERROR: Failed to push to repository."
    exit 1
fi

echo "Repository $REPO_NAME created/updated and initialized with current directory contents"
echo "Using SSH URL: $REPO_URL"

# Verify the remote URL is using SSH
REMOTE_URL=$(git remote get-url origin)
if [[ "$REMOTE_URL" != git@* ]]; then
    echo "WARNING: Remote URL is not using SSH format. Current URL: $REMOTE_URL"
    echo "Updating to SSH URL: $REPO_URL"
    git remote set-url origin "$REPO_URL"
    echo "Remote URL updated to use SSH"
fi