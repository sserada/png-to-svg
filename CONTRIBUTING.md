# Contributing to PNG to SVG Converter

Thank you for your interest in contributing to the PNG to SVG Converter project! We welcome contributions from everyone.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 16+ (for local frontend development)
- Python 3.10+ (for local backend development)
- Git

### Setting Up Development Environment

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/png-to-svg.git
   cd png-to-svg
   ```

3. Set up environment variables:
   ```bash
   cp sample.env .env
   ```

4. Start the development environment:
   ```bash
   docker-compose up -d
   ```

5. Access the application:
   - Frontend: http://localhost:55030
   - Backend API: http://localhost:55031

### Project Structure

```
png-to-svg/
├── frontend/          # SvelteKit frontend application
│   ├── src/
│   │   ├── routes/   # SvelteKit routes
│   │   └── lib/      # Shared libraries and utilities
│   └── Dockerfile
├── backend/           # FastAPI backend application
│   ├── main.py       # Main application file
│   ├── requirements.txt
│   └── Dockerfile
├── .github/          # GitHub templates and workflows
└── compose.yml       # Docker Compose configuration
```

## Development Workflow

### 1. Create an Issue

Before starting work on a new feature or bug fix, **always create an issue first** or find an existing one to work on. This helps:
- Avoid duplicate work
- Get feedback on your approach
- Track progress

### 2. Create a Branch

Create a new branch from `main` using the following naming convention:

- Feature: `feature/issue-{number}-short-description`
- Bug fix: `fix/issue-{number}-short-description`
- Documentation: `docs/issue-{number}-short-description`
- Refactoring: `refactor/issue-{number}-short-description`

Example:
```bash
git checkout -b feature/issue-42-add-batch-processing
```

### 3. Make Your Changes

- Write clean, readable code
- Follow the coding standards (see below)
- Add tests for new functionality
- Update documentation as needed

### 4. Test Your Changes

- Ensure all existing tests pass
- Add new tests for your changes
- Test manually in the Docker environment

### 5. Commit Your Changes

Follow the commit message guidelines (see below).

```bash
git add .
git commit -m "feat: add batch processing for multiple files"
```

### 6. Push and Create a Pull Request

```bash
git push origin feature/issue-42-add-batch-processing
```

Then create a Pull Request on GitHub, linking it to the related issue.

## Coding Standards

### Frontend (SvelteKit/TypeScript)

- Use TypeScript for type safety
- Follow the existing code style
- Use meaningful variable and function names
- Keep components small and focused
- Use Svelte's reactive statements appropriately

**Linting:**
```bash
cd frontend
npm run lint
```

**Formatting:**
```bash
cd frontend
npm run format
```

### Backend (Python/FastAPI)

- Follow PEP 8 style guide
- Use type hints for function parameters and return values
- Write docstrings for functions and classes
- Keep functions small and focused
- Handle errors appropriately

**Linting (recommended):**
```bash
cd backend
pip install ruff
ruff check .
```

**Formatting (recommended):**
```bash
pip install black
black .
```

## Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that don't affect code meaning (formatting, etc.)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Changes to build process or auxiliary tools

### Examples

```
feat(backend): add VTracer integration for true vectorization

- Implement VTracer library for PNG to SVG conversion
- Add conversion parameters (color mode, filter speckle, etc.)
- Update requirements.txt with vtracer dependency

Closes #42
```

```
fix(frontend): resolve file upload error on Safari

- Fix FileReader compatibility issue
- Add proper error handling for unsupported browsers

Fixes #38
```

## Pull Request Process

1. **Link to Issue**: Always reference the related issue in your PR description using `Closes #123` or `Fixes #123`

2. **Fill Out Template**: Complete all sections of the Pull Request template

3. **Update Documentation**: If your changes affect user-facing functionality, update the README.md and relevant documentation

4. **Pass All Checks**: Ensure all tests and linting checks pass

5. **Request Review**: Request review from maintainers

6. **Address Feedback**: Respond to review comments and make requested changes

7. **Squash Commits** (optional): Consider squashing commits before merge to keep history clean

### PR Checklist

- [ ] Issue created and linked
- [ ] Branch follows naming convention
- [ ] Code follows style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] PR template filled out completely

## Testing

### Frontend Testing

(Note: Testing framework to be set up in Phase 4)

```bash
cd frontend
npm test
```

### Backend Testing

(Note: Testing framework to be set up in Phase 4)

```bash
cd backend
pytest
```

### Manual Testing

Always test your changes in the Docker environment:

```bash
docker-compose up --build
```

Test the following scenarios:
- Upload single PNG file
- Upload multiple PNG files
- Download converted SVG files
- Error handling (invalid files, network errors, etc.)

## Documentation

### When to Update Documentation

- Adding new features
- Changing existing behavior
- Updating dependencies
- Modifying setup/installation process

### What to Document

- **README.md**: User-facing features and setup instructions
- **Code Comments**: Complex logic and non-obvious decisions
- **Docstrings**: All public functions and classes
- **CHANGELOG** (to be added): All notable changes

## Questions or Need Help?

- Open an issue with the `question` label
- Check existing issues and discussions
- Review the [README.md](README.md) for basic information

## Recognition

Contributors will be recognized in:
- Git commit history
- Future CONTRIBUTORS.md file (to be created)
- Project acknowledgments

Thank you for contributing to PNG to SVG Converter!
