"""Tests for release version parsing and comparison utilities."""

import pytest

from devflow.release.version import (
    Version,
    detect_release_type,
    get_next_dev_version,
    validate_version_files,
)


class TestVersionParsing:
    """Test version string parsing."""

    def test_parse_release_version(self):
        """Test parsing a release version (no -dev suffix)."""
        v = Version.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.dev is False

    def test_parse_dev_version(self):
        """Test parsing a development version (with -dev suffix)."""
        v = Version.parse("1.2.3-dev")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.dev is True

    def test_parse_version_with_whitespace(self):
        """Test parsing version with surrounding whitespace."""
        v = Version.parse("  1.2.3-dev  ")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.dev is True

    def test_parse_invalid_format(self):
        """Test parsing invalid version formats."""
        with pytest.raises(ValueError, match="Invalid version format"):
            Version.parse("1.2")

        with pytest.raises(ValueError, match="Invalid version format"):
            Version.parse("1.2.3.4")

        with pytest.raises(ValueError, match="Invalid version format"):
            Version.parse("v1.2.3")

        with pytest.raises(ValueError, match="Invalid version format"):
            Version.parse("1.2.3-alpha")

    def test_str_representation(self):
        """Test string representation of versions."""
        v1 = Version(1, 2, 3, dev=False)
        assert str(v1) == "1.2.3"

        v2 = Version(1, 2, 3, dev=True)
        assert str(v2) == "1.2.3-dev"


class TestVersionManipulation:
    """Test version manipulation methods."""

    def test_without_dev(self):
        """Test removing -dev suffix."""
        v = Version(1, 2, 3, dev=True)
        v_clean = v.without_dev()
        assert v_clean.major == 1
        assert v_clean.minor == 2
        assert v_clean.patch == 3
        assert v_clean.dev is False

    def test_with_dev(self):
        """Test adding -dev suffix."""
        v = Version(1, 2, 3, dev=False)
        v_dev = v.with_dev()
        assert v_dev.major == 1
        assert v_dev.minor == 2
        assert v_dev.patch == 3
        assert v_dev.dev is True

    def test_bump_major(self):
        """Test bumping major version."""
        v = Version(1, 2, 3, dev=True)
        v_bumped = v.bump_major()
        assert v_bumped.major == 2
        assert v_bumped.minor == 0
        assert v_bumped.patch == 0
        assert v_bumped.dev is False

    def test_bump_minor(self):
        """Test bumping minor version."""
        v = Version(1, 2, 3, dev=True)
        v_bumped = v.bump_minor()
        assert v_bumped.major == 1
        assert v_bumped.minor == 3
        assert v_bumped.patch == 0
        assert v_bumped.dev is False

    def test_bump_patch(self):
        """Test bumping patch version."""
        v = Version(1, 2, 3, dev=True)
        v_bumped = v.bump_patch()
        assert v_bumped.major == 1
        assert v_bumped.minor == 2
        assert v_bumped.patch == 4
        assert v_bumped.dev is False


class TestReleaseTypeDetection:
    """Test release type detection."""

    def test_detect_major_release(self):
        """Test detecting major release."""
        current = Version.parse("1.9.5-dev")
        target = Version.parse("2.0.0")
        release_type = detect_release_type(current, target)
        assert release_type == "major"

    def test_detect_minor_release(self):
        """Test detecting minor release."""
        current = Version.parse("1.2.5-dev")
        target = Version.parse("1.3.0")
        release_type = detect_release_type(current, target)
        assert release_type == "minor"

    def test_detect_patch_release(self):
        """Test detecting patch release."""
        current = Version.parse("1.2.3")
        target = Version.parse("1.2.4")
        release_type = detect_release_type(current, target)
        assert release_type == "patch"

    def test_detect_invalid_major_release_non_zero_minor(self):
        """Test that major release must have minor=0 and patch=0."""
        current = Version.parse("1.2.3-dev")
        target = Version.parse("2.1.0")
        with pytest.raises(ValueError, match="Major release should be 2.0.0"):
            detect_release_type(current, target)

    def test_detect_invalid_major_release_non_zero_patch(self):
        """Test that major release must have patch=0."""
        current = Version.parse("1.2.3-dev")
        target = Version.parse("2.0.1")
        with pytest.raises(ValueError, match="Major release should be 2.0.0"):
            detect_release_type(current, target)

    def test_detect_invalid_minor_release_non_zero_patch(self):
        """Test that minor release must have patch=0."""
        current = Version.parse("1.2.3-dev")
        target = Version.parse("1.3.1")
        with pytest.raises(ValueError, match="Minor release should be 1.3.0"):
            detect_release_type(current, target)

    def test_detect_invalid_target_with_dev_suffix(self):
        """Test that target version cannot have -dev suffix."""
        current = Version.parse("1.2.3-dev")
        target = Version.parse("1.3.0-dev")
        with pytest.raises(ValueError, match="Target version cannot have -dev suffix"):
            detect_release_type(current, target)

    def test_detect_invalid_backwards_version(self):
        """Test that target must be greater than current."""
        current = Version.parse("1.3.0-dev")
        target = Version.parse("1.2.0")
        with pytest.raises(ValueError, match="Invalid version progression"):
            detect_release_type(current, target)

    def test_detect_completing_dev_cycle_minor(self):
        """Test that completing a -dev cycle is detected correctly (minor)."""
        current = Version.parse("1.2.0-dev")
        target = Version.parse("1.2.0")
        release_type = detect_release_type(current, target)
        assert release_type == "minor"

    def test_detect_completing_dev_cycle_major(self):
        """Test that completing a -dev cycle is detected correctly (major)."""
        current = Version.parse("1.0.0-dev")
        target = Version.parse("1.0.0")
        release_type = detect_release_type(current, target)
        assert release_type == "major"

    def test_detect_completing_dev_cycle_patch(self):
        """Test that completing a -dev cycle is detected correctly (patch)."""
        current = Version.parse("1.2.3-dev")
        target = Version.parse("1.2.3")
        release_type = detect_release_type(current, target)
        assert release_type == "patch"


class TestNextDevVersion:
    """Test calculating next development version."""

    def test_next_dev_after_minor_release(self):
        """Test next dev version after minor release (bump minor for main)."""
        release = Version.parse("1.2.0")
        next_dev = get_next_dev_version(release, "minor")
        assert str(next_dev) == "1.3.0-dev"

    def test_next_dev_after_major_release(self):
        """Test next dev version after major release (bump minor for main)."""
        release = Version.parse("2.0.0")
        next_dev = get_next_dev_version(release, "major")
        assert str(next_dev) == "2.1.0-dev"

    def test_next_dev_after_patch_release(self):
        """Test next dev version after patch release (bump patch for release branch)."""
        release = Version.parse("1.2.3")
        next_dev = get_next_dev_version(release, "patch")
        assert str(next_dev) == "1.2.4-dev"


class TestVersionFileValidation:
    """Test version file validation."""

    def test_validate_matching_versions(self):
        """Test validation when versions match."""
        version, match = validate_version_files("1.2.3", "1.2.3")
        assert str(version) == "1.2.3"
        assert match is True

    def test_validate_matching_dev_versions(self):
        """Test validation when dev versions match."""
        version, match = validate_version_files("1.2.3-dev", "1.2.3-dev")
        assert str(version) == "1.2.3-dev"
        assert match is True

    def test_validate_mismatched_versions(self):
        """Test validation when versions don't match."""
        version, match = validate_version_files("1.2.3", "1.2.4")
        assert str(version) == "1.2.3"
        assert match is False

    def test_validate_dev_mismatch(self):
        """Test validation when one has -dev and one doesn't."""
        version, match = validate_version_files("1.2.3-dev", "1.2.3")
        assert str(version) == "1.2.3-dev"
        assert match is False

    def test_validate_invalid_init_version(self):
        """Test validation with invalid __init__.py version."""
        with pytest.raises(ValueError, match="Invalid version format"):
            validate_version_files("invalid", "1.2.3")

    def test_validate_invalid_setup_version(self):
        """Test validation with invalid setup.py version."""
        with pytest.raises(ValueError, match="Invalid version format"):
            validate_version_files("1.2.3", "invalid")


class TestVersionComparison:
    """Test version comparison for edge cases."""

    def test_major_release_from_zero(self):
        """Test major release from 0.x.x to 1.0.0."""
        current = Version.parse("0.9.5-dev")
        target = Version.parse("1.0.0")
        release_type = detect_release_type(current, target)
        assert release_type == "major"

    def test_minor_release_after_major(self):
        """Test minor release after a major release (e.g., 2.0.0-dev -> 2.1.0)."""
        current = Version.parse("2.0.0-dev")
        target = Version.parse("2.1.0")
        release_type = detect_release_type(current, target)
        assert release_type == "minor"

    def test_patch_release_from_first_minor(self):
        """Test patch release from X.0.0 to X.0.1."""
        current = Version.parse("1.0.0")
        target = Version.parse("1.0.1")
        release_type = detect_release_type(current, target)
        assert release_type == "patch"

    def test_skip_minor_version(self):
        """Test that skipping minor versions is detected as minor release."""
        current = Version.parse("1.2.0-dev")
        target = Version.parse("1.4.0")
        release_type = detect_release_type(current, target)
        assert release_type == "minor"

    def test_skip_patch_version(self):
        """Test that skipping patch versions is detected as patch release."""
        current = Version.parse("1.2.3")
        target = Version.parse("1.2.5")
        release_type = detect_release_type(current, target)
        assert release_type == "patch"
