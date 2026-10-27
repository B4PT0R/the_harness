from the_harness import project_paths


def test_source_checkout_resources():
    root = project_paths.PROJECT_ROOT
    assert (root / "package.json").is_file()
    assert (root / "desktop/src/main.jsx").is_file()
    assert (root / "ui/package.json").is_file()
    assert (root / "assets/assistant-tray.png").is_file()


def test_installed_resources_do_not_use_site_packages_root(tmp_path, monkeypatch):
    package = tmp_path / "site-packages/the_harness"
    bundled = package / "_project"
    bundled.mkdir(parents=True)
    monkeypatch.setattr(project_paths, "__file__", str(package / "project_paths.py"))
    assert project_paths.project_root() == bundled


def test_source_resources_use_project_root(tmp_path, monkeypatch):
    package = tmp_path / "checkout/the_harness"
    monkeypatch.setattr(project_paths, "__file__", str(package / "project_paths.py"))
    assert project_paths.project_root() == package.parent


def test_application_uses_distribution_version():
    from importlib.metadata import version
    from the_harness.application import application

    assert application.version == version("b4pt0r-the-harness")
