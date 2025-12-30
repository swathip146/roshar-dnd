# Fresh Repository Setup Guide

## Problem
Your current GitHub repository (`https://github.com/swathip146/roshar-dnd`) contains sensitive/restricted access code in its git history. Even if you delete files now, the history still contains them.

## Solution
Create a completely fresh repository without any git history. This will:
- ✅ Remove all git history (including sensitive data)
- ✅ Start with a clean slate
- ✅ Keep all your current code
- ✅ Allow you to push to a new GitHub repository

## ⚠️ IMPORTANT: Before You Start

### 1. Check for Sensitive Files
Before creating the fresh repo, verify that sensitive files are excluded:

```bash
# Check for common sensitive files
ls -la | grep -E "\.env|secrets|api.*key|password|token"
```

### 2. Verify .gitignore
Make sure your `.gitignore` properly excludes:
- API keys and secrets (`.env`, `secrets.json`, etc.)
- Configuration files with sensitive data
- Cache files
- Personal data

### 3. Backup Your Current Work
Even though we're keeping your files, it's good practice:
```bash
# Create a backup (optional but recommended)
cd ..
cp -r roshar-dnd roshar-dnd-backup
```

## Step-by-Step Instructions

### Option 1: Use the Automated Script (Recommended)

1. **Run the script:**
   ```bash
   cd /Users/patnaiku/projects/roshar-dnd
   ./create_fresh_repo.sh
   ```

2. **Create a new GitHub repository:**
   - Go to https://github.com/new
   - Choose a new name (e.g., `roshar-dnd-clean`)
   - **DO NOT** initialize with README, .gitignore, or license
   - Click "Create repository"

3. **Connect and push:**
   ```bash
   # Replace <YOUR_NEW_REPO_URL> with your actual new repo URL
   git remote add origin <YOUR_NEW_REPO_URL>
   git branch -M main
   git push -u origin main
   ```

4. **Verify the new repository:**
   - Check that all files are present
   - Verify no sensitive data is exposed
   - Test that the code works

5. **Delete the old repository:**
   - Go to https://github.com/swathip146/roshar-dnd/settings
   - Scroll to "Danger Zone"
   - Click "Delete this repository"
   - Type the repository name to confirm

### Option 2: Manual Steps

If you prefer to do it manually:

```bash
# 1. Remove old git history
rm -rf .git

# 2. Initialize fresh repository
git init

# 3. Add all files
git add .

# 4. Create initial commit
git commit -m "Initial commit - fresh repository without history"

# 5. Create new GitHub repo (via web interface), then:
git remote add origin <YOUR_NEW_REPO_URL>
git branch -M main
git push -u origin main
```

## What This Solves

✅ **Removes all git history** - No sensitive data in commits  
✅ **Clean start** - Fresh repository with only current code  
✅ **No history exposure** - Old commits won't be accessible  
✅ **Keeps your code** - All current files remain intact  

## What This Doesn't Solve

⚠️ **If sensitive data was already pushed to GitHub**, you should:
1. Consider the data compromised
2. Rotate any API keys, tokens, or credentials that were exposed
3. Review GitHub's security advisories if needed

## Verification Checklist

After setting up the new repository:

- [ ] All files are present in the new repo
- [ ] No `.env` or sensitive config files are visible
- [ ] `.gitignore` is properly configured
- [ ] Code runs correctly
- [ ] Old repository is deleted (after verification)
- [ ] Team members are notified of the new repository URL

## Common Issues

### Issue: "Remote origin already exists"
**Solution:**
```bash
git remote remove origin
git remote add origin <YOUR_NEW_REPO_URL>
```

### Issue: "Branch name mismatch"
**Solution:**
```bash
git branch -M main  # Rename current branch to main
```

### Issue: "Permission denied"
**Solution:**
- Make sure you have write access to the new repository
- Check your GitHub authentication (SSH keys or personal access token)

## Security Best Practices Going Forward

1. **Never commit sensitive data** - Use `.gitignore` and environment variables
2. **Use git-secrets or pre-commit hooks** - Scan for secrets before committing
3. **Review before pushing** - `git diff` before committing
4. **Use environment variables** - Store secrets in `.env` files (gitignored)
5. **Rotate exposed credentials** - If something was exposed, change it immediately

## Need Help?

If you encounter issues:
1. Check that all sensitive files are in `.gitignore`
2. Verify your GitHub authentication
3. Ensure the new repository exists and is empty
4. Check file permissions

