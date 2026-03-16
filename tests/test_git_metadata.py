"""
Git metadata preservation tests for codebases.

Tests that git_url and git_branch are preserved when codebases are
rehydrated from database or updated.
"""
import pytest
import asyncio
from datetime import datetime
from a2a_server.agent_bridge import (
    RegisteredCodebase,
    OpenCodeBridge,
    AgentStatus,
)


class TestGitMetadata:
    """Test that git metadata is preserved in RegisteredCodebase."""

    def test_codebase_git_fields_exist(self):
        """Test that RegisteredCodebase has git_url and git_branch fields."""
        codebase = RegisteredCodebase(
            id="test-cb-1",
            name="Test Repo",
            path="/tmp/test",
            git_url="https://github.com/test/repo.git",
            git_branch="develop",
        )
        assert codebase.git_url == "https://github.com/test/repo.git"
        assert codebase.git_branch == "develop"

    def test_codebase_git_defaults(self):
        """Test that git fields have proper defaults."""
        codebase = RegisteredCodebase(
            id="test-cb-2",
            name="Local Repo",
            path="/tmp/local",
        )
        assert codebase.git_url is None
        assert codebase.git_branch == "main"

    def test_codebase_to_dict_includes_git_fields(self):
        """Test that to_dict() includes git metadata."""
        codebase = RegisteredCodebase(
            id="test-cb-3",
            name="Git Project",
            path="/tmp/git",
            git_url="https://github.com/example/test.git",
            git_branch="feature-branch",
        )
        result = codebase.to_dict()
        
        assert "git_url" in result
        assert "git_branch" in result
        assert result["git_url"] == "https://github.com/example/test.git"
        assert result["git_branch"] == "feature-branch"

    def test_codebase_to_dict_with_null_git_url(self):
        """Test that to_dict() handles None git_url correctly."""
        codebase = RegisteredCodebase(
            id="test-cb-4",
            name="Local Project",
            path="/tmp/local",
            git_url=None,
            git_branch="main",
        )
        result = codebase.to_dict()
        
        assert "git_url" in result
        assert "git_branch" in result
        assert result["git_url"] is None
        assert result["git_branch"] == "main"

    @pytest.mark.asyncio
    async def test_bridge_save_and_retrieve_git_metadata(self):
        """Test that git metadata is preserved through save/retrieve cycle."""
        bridge = OpenCodeBridge()
        
        codebase = RegisteredCodebase(
            id="git-cb-123",
            name="Git Repo",
            path="/tmp/git-repo",
            git_url="https://github.com/test/repo.git",
            git_branch="main",
            status=AgentStatus.IDLE,
        )
        
        # Save the codebase (this updates the in-memory dict)
        await bridge._save_codebase(codebase)
        
        # Verify the in-memory codebase still has git fields
        fetched = bridge.get_codebase("git-cb-123")
        assert fetched is not None
        assert fetched.git_url == "https://github.com/test/repo.git"
        assert fetched.git_branch == "main"
        
        # Verify to_dict includes git fields
        result = fetched.to_dict()
        assert result["git_url"] == "https://github.com/test/repo.git"
        assert result["git_branch"] == "main"

    @pytest.mark.asyncio
    async def test_bridge_register_codebase_with_git_metadata(self):
        """Test that register_codebase preserves git metadata."""
        bridge = OpenCodeBridge()
        
        # Register a codebase with git metadata
        codebase = await bridge.register_codebase(
            name="Git Project",
            path="/tmp/git-project",
            description="A git-backed project",
            codebase_id="git-reg-cb",
        )
        
        # Update with git metadata (simulating rehydration from DB)
        codebase.git_url = "https://github.com/rehydrated/repo.git"
        codebase.git_branch = "production"
        await bridge._save_codebase(codebase)
        
        # Fetch and verify
        fetched = bridge.get_codebase("git-reg-cb")
        assert fetched is not None
        assert fetched.git_url == "https://github.com/rehydrated/repo.git"
        assert fetched.git_branch == "production"

    @pytest.mark.asyncio
    async def test_bridge_load_codebases_from_db_preserves_git(self):
        """Test that _load_codebases_from_db preserves git metadata.
        
        This simulates the scenario where:
        1. Codebase is registered with git metadata
        2. Server restarts
        3. Codebases are rehydrated from database
        4. Git metadata should be preserved
        """
        bridge = OpenCodeBridge()
        
        # Create a codebase with git metadata
        codebase = RegisteredCodebase(
            id="db-git-cb",
            name="DB Git Project",
            path="/tmp/db-git",
            git_url="https://github.com/db/test.git",
            git_branch="staging",
            status=AgentStatus.IDLE,
        )
        
        # Manually add to in-memory cache
        bridge._codebases["db-git-cb"] = codebase
        
        # Verify the codebase preserves git metadata
        fetched = bridge.get_codebase("db-git-cb")
        assert fetched is not None
        assert fetched.git_url == "https://github.com/db/test.git"
        assert fetched.git_branch == "staging"
        assert fetched.to_dict()["git_url"] == "https://github.com/db/test.git"
        assert fetched.to_dict()["git_branch"] == "staging"

    @pytest.mark.asyncio
    async def test_register_codebase_with_git_params(self):
        """Test that register_codebase accepts and preserves git metadata params."""
        bridge = OpenCodeBridge()
        
        # Register a codebase with git metadata directly via params
        codebase = await bridge.register_codebase(
            name="Git Param Project",
            path="/tmp/git-param-project",
            description="A git-backed project",
            codebase_id="git-param-cb",
            git_url="https://github.com/param/test.git",
            git_branch="feature-xyz",
        )
        
        # Verify the git metadata is preserved
        assert codebase.git_url == "https://github.com/param/test.git"
        assert codebase.git_branch == "feature-xyz"
        
        # Verify to_dict includes git metadata
        result = codebase.to_dict()
        assert result["git_url"] == "https://github.com/param/test.git"
        assert result["git_branch"] == "feature-xyz"
        
        # Verify retrieval also preserves git metadata
        fetched = bridge.get_codebase("git-param-cb")
        assert fetched is not None
        assert fetched.git_url == "https://github.com/param/test.git"
        assert fetched.git_branch == "feature-xyz"

    @pytest.mark.asyncio
    async def test_register_codebase_update_preserves_git_metadata(self):
        """Test that updating an existing codebase preserves git metadata."""
        bridge = OpenCodeBridge()
        
        # Register a codebase with git metadata
        codebase = await bridge.register_codebase(
            name="Update Test Project",
            path="/tmp/update-test-project",
            description="Original description",
            codebase_id="update-test-cb",
            git_url="https://github.com/update/test.git",
            git_branch="develop",
        )
        
        # Update the codebase (simulating re-registration after restart)
        updated = await bridge.register_codebase(
            name="Updated Project Name",
            path="/tmp/update-test-project",
            description="Updated description",
            codebase_id="update-test-cb",
            git_url="https://github.com/update/test.git",
            git_branch="develop",
        )
        
        # Verify git metadata is preserved
        assert updated.git_url == "https://github.com/update/test.git"
        assert updated.git_branch == "develop"
        assert updated.name == "Updated Project Name"

    def test_database_row_to_codebase_includes_git(self):
        """Test that _row_to_codebase in database.py includes git fields."""
        from a2a_server.database import _row_to_codebase
        
        # Simulate a database row with git metadata
        mock_row = {
            'id': 'row-test-cb',
            'name': 'Row Test',
            'path': '/tmp/row-test',
            'description': 'Test from row',
            'worker_id': None,
            'agent_config': '{}',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'status': 'idle',
            'session_id': None,
            'opencode_port': None,
            'minio_path': None,
            'last_sync_at': None,
            'git_url': 'https://github.com/row/test.git',
            'git_branch': 'release',
        }
        
        result = _row_to_codebase(mock_row)
        
        assert 'git_url' in result
        assert 'git_branch' in result
        assert result['git_url'] == 'https://github.com/row/test.git'
        assert result['git_branch'] == 'release'
