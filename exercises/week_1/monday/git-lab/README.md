# Lab: Git Workflow & Conflict Resolution

## Objectives
- Initialize a local Git repository and configure user details.
- Record changes by creating commits.
- Create and navigate between Git branches.
- Merge branches and resolve a merge conflict manually.
- Use a `.gitignore` file to ignore untracked files.

---

## Tasks

### Task 1: Repository Initialization
1. Open a terminal and navigate to the directory where you want to initialize your practice repo.
2. Initialize a new Git repository:
   ```bash
   git init git-practice-lab
   cd git-practice-lab
   ```
3. Copy the starter file `app_config.txt` from this lab's `starter_code/app_config.txt` into your new `git-practice-lab` folder.
4. Check the status of your repository:
   ```bash
   git status
   ```

### Task 2: Initial Commit
1. Configure your local git name and email if you haven't already:
   ```bash
   git config user.name "Your Name"
   git config user.email "your.email@example.com"
   ```
2. Stage the configuration file:
   ```bash
   git add app_config.txt
   ```
3. Create your initial commit:
   ```bash
   git commit -m "Initial commit: Add default app configuration"
   ```

### Task 3: Feature Branch Changes
1. Create and switch to a new branch named `feature-scaling`:
   ```bash
   git checkout -b feature-scaling
   ```
2. Open `app_config.txt` and modify the `MAX_CONNECTIONS` parameter on line 6 to:
   ```text
   MAX_CONNECTIONS=100
   ```
3. Stage and commit this change on the branch:
   ```bash
   git add app_config.txt
   git commit -m "Scale max connections to 100 for high traffic load"
   ```

### Task 4: Conflicting Main Branch Changes
1. Switch back to the `main` branch:
   ```bash
   git checkout main
   ```
2. Open `app_config.txt`. Notice that `MAX_CONNECTIONS` is back to `20`.
3. In parallel, another ticket request asks you to limit connections to `10` on the main branch for testing. Update line 6 to:
   ```text
   MAX_CONNECTIONS=10
   ```
4. Stage and commit this change on `main`:
   ```bash
   git add app_config.txt
   git commit -m "Reduce max connections to 10 for resource limits test"
   ```

### Task 5: Trigger and Resolve the Conflict
1. Attempt to merge the `feature-scaling` branch into `main`:
   ```bash
   git merge feature-scaling
   ```
2. Git will report a conflict:
   ```text
   CONFLICT (content): Merge conflict in app_config.txt
   Automatic merge failed; fix conflicts and then commit the result.
   ```
3. Open `app_config.txt` in a text editor. Locate the conflict markers:
   ```text
   <<<<<<< HEAD
   MAX_CONNECTIONS=10
   =======
   MAX_CONNECTIONS=100
   >>>>>>> feature-scaling
   ```
4. Manually resolve the conflict by deciding to merge the values. Change the line to:
   ```text
   MAX_CONNECTIONS=100
   ```
5. Remove all conflict marker lines (`<<<<<<<`, `=======`, `>>>>>>>`).
6. Save the file.
7. Stage the resolved file and commit:
   ```bash
   git add app_config.txt
   git commit -m "Merge branch 'feature-scaling' and resolve MAX_CONNECTIONS conflict"
   ```

### Task 6: Adding a Gitignore
1. Create a file named `.gitignore` in your repository root.
2. Add the following lines to ignore Python bytecode and environment files:
   ```text
   __pycache__/
   *.pyc
   .env
   ```
3. Stage and commit the `.gitignore` file:
   ```bash
   git add .gitignore
   git commit -m "Add .gitignore for python cache and secrets"
   ```

---

## Definition of Done
- A local git repository contains `app_config.txt` and `.gitignore`.
- Running `git log --oneline --graph` shows the commit history and the merge fork/join.
- The final `MAX_CONNECTIONS` value in `app_config.txt` on the `main` branch is `100`.
