#!/usr/bin/env python

"""Tests for `version_differ` package."""

import tempfile
from git import Repo
from pygit2 import clone_repository


from version_differ.version_differ import *
from version_differ.download import *


def test_src_download_url():
    assert (
        get_package_version_source_url(CARGO, "depdive", "0.1.0")
        == "https://crates.io/api/v1/crates/depdive/0.1.0/download"
    )
    assert (
        get_package_version_source_url(COMPOSER, "psr/log", "2.0.0")
        == "https://api.github.com/repos/php-fig/log/zipball/ef29f6d262798707a9edd554e2b82517ef3a9376"
    )
    assert (
        get_package_version_source_url(NPM, "lodash", "4.11.1")
        == "https://registry.npmjs.org/lodash/-/lodash-4.11.1.tgz"
    )
    assert (
        get_package_version_source_url(PIP, "Django", "3.2.7")
        == "https://files.pythonhosted.org/packages/27/1c/6fe40cdfdbbc8a0d7c211dde68777f1d435bde7879697d0bc20c73d136ac/Django-3.2.7-py3-none-any.whl"
    )
    assert (
        get_package_version_source_url(RUBYGEMS, "bundler", "2.2.27")
        == "https://rubygems.org/downloads/bundler-2.2.27.gem"
    )
    assert (
        get_package_version_source_url(MAVEN, "io.spray:spray-httpx", "1.2.3")
        == "https://repo1.maven.org/maven2/io/spray/spray-httpx/1.2.3/spray-httpx-1.2.3-sources.jar"
    )


def test_get_commit_of_release():
    temp_dir = tempfile.TemporaryDirectory()
    url = "https://github.com/nasifimtiazohi/test-version-tag"
    package = "test"
    clone_repository(url, temp_dir.name)

    repo = Repo(temp_dir.name)
    tags = repo.tags

    assert get_commit_of_release(tags, package, "0.0.8") is None
    assert get_commit_of_release(tags, package, "10.0.8").hexsha == "51efd612af12183a682bb3242d41369d2879ad60"
    assert get_commit_of_release(tags, package, "10.0.8-") is None
    assert get_commit_of_release(tags, "hakari", "0.3.0").hexsha == "946ddf053582067b843c19f1270fe92eaa0a7cb3"

    temp_dir = tempfile.TemporaryDirectory()
    url = "https://github.com/rayon-rs/rayon"
    clone_repository(url, temp_dir.name)

    repo = Repo(temp_dir.name)
    tags = repo.tags
    assert get_commit_of_release(tags, "rayon", "1.5.0") is None
    get_commit_of_release(tags, "rayon-core", "1.5.0") == "b8b97a17bc4cbef89807444566eee7cdc523b7d1"

    temp_dir = tempfile.TemporaryDirectory()
    url = "https://github.com/tokio-rs/tokio"
    clone_repository(url, temp_dir.name)

    repo = Repo(temp_dir.name)
    tags = repo.tags
    assert get_commit_of_release(tags, "tokio", "1.5.0").hexsha == "a5ee2f0d3d78daa01e2c6c12d22b82474dc5c32a"
    assert get_commit_of_release(tags, "tokio-macros", "1.5.0").hexsha == "bb6a292d0a7f4fdd18f723a882b2ed04c17c42d7"
    assert get_commit_of_release(tags, "tokio-util", "1.5.0") is None

    assert get_commit_of_release(tags, "tokio-uds", "0.2.0").hexsha == "06325fa63b456069a7003b4fbf2dc1ac980c9a44"
    assert get_commit_of_release(tags, "tokio-tls", "0.2.0").hexsha == "89d6bfc5cb431686d59b6659c6aa0a8531a87dff"


def test_get_go_module_path():
    assert get_go_module_path("github.com/keybase/client/go/chat/attachments") == "go/chat/attachments"
    assert not get_go_module_path("github.com/lightningnetwork/lnd")
    assert get_go_module_path("github.com/istio/istio/pilot/pkg/proxy/envoy/v2") == "pilot/pkg/proxy/envoy/v2"


def test_go():
    assert (
        get_files_loc_stat(
            get_version_diff_stats(
                GO,
                "github.com/labstack/echo/middleware",
                "4.1.17",
                "4.2.0",
                "https://github.com/labstack/echo",
            )
        )
        == (27, 2461, 234)
    )

    assert (
        get_files_loc_stat(
            get_version_diff_stats(
                GO,
                "github.com/crewjam/saml",
                "0.4.2",
                "0.4.3",
                "https://github.com/crewjam/saml",
            )
        )
        == (10, 179, 13)
    )


def get_sha_stat(output):
    return (
        output.old_version_git_sha,
        output.new_version_git_sha,
    )


def get_files_loc_stat(output):
    # for k in files.keys():
    #     print(k, "\n::::::::::::::::::::::::::::::::::::::::\n", files[k])

    files = output.diff
    changed_files = len(files)
    lines_added = lines_removed = 0
    for k in files.keys():
        lines_added += files[k].loc_added
        lines_removed += files[k].loc_removed
    return changed_files, lines_added, lines_removed


def test_composer():
    assert get_files_loc_stat(get_version_diff_stats(COMPOSER, "psr/log", "1.1.4", "2.0.0")) == (10, 56, 430)

    assert (
        get_files_loc_stat(
            get_version_diff_stats(
                COMPOSER,
                "illuminate/auth",
                "4.1.25",
                "4.1.26",
            )
        )
        == (6, 186, 13)
    )


def test_maven():
    assert (
        get_files_loc_stat(
            get_version_diff_stats(
                MAVEN,
                "com.github.junrar:junrar",
                "1.0.0",
                "1.0.1",
            )
        )
        == (8, 40, 125)
    )

    assert (
        get_files_loc_stat(
            get_version_diff_stats(
                MAVEN,
                "org.togglz:togglz-console",
                "2.9.3",
                "2.9.4",
            )
        )
        == (8, 88, 2)
    )


def test_npm():
    assert get_files_loc_stat(get_version_diff_stats(NPM, "lodash", "4.11.0", "4.11.1")) == (12, 54, 44)

    output = get_version_diff_stats(
        NPM,
        "set-value",
        "3.0.0",
        "3.0.1",
    )
    assert get_files_loc_stat(output) == (4, 23, 25)

    assert len(output.new_version_filelist) == 4


def test_nuget():
    assert (
        get_files_loc_stat(
            get_version_diff_stats(
                NUGET,
                "messagepack.immutablecollection",
                "2.0.335",
                "2.1.80",
                "https://github.com/neuecc/MessagePack-CSharp",
            )
        )
        == (1, 14, 6)
    )

    assert (
        get_files_loc_stat(
            get_version_diff_stats(
                NUGET,
                "microsoft.aspnetcore.server.kestrel.core",
                "2.0.2",
                "2.0.3",
                "https://github.com/aspnet/KestrelHttpServer",
            )
        )
        == (7, 89, 24)
    )


def test_pip():
    assert get_files_loc_stat(get_version_diff_stats(PIP, "meinheld", "1.0.1", "1.0.2")) == (43, 6091, 6380)

    assert get_files_loc_stat(get_version_diff_stats(PIP, "django", "3.1.6", "3.1.7")) == (3, 5, 2)

    assert get_files_loc_stat(get_version_diff_stats(PIP, "azure-storage-blob", "12.8.0", "12.8.1")) == (24, 773, 457)

    output = get_version_diff_stats(PIP, "numpy", "1.21.4", "1.21.5")
    assert get_files_loc_stat(output) == (14, 208, 55)
    assert len(output.new_version_filelist) == 706


def test_rubygems():
    # in below example, auto-generated file spec/example.txt causes a large diff
    assert get_files_loc_stat(get_version_diff_stats(RUBYGEMS, "yard", "0.9.19", "0.9.20")) == (10, 1706, 1696)

    assert get_files_loc_stat(get_version_diff_stats(RUBYGEMS, "bundler", "2.2.31", "2.2.32")) == (7, 45, 70)

    assert get_files_loc_stat(get_version_diff_stats(RUBYGEMS, "excon", "0.9.5", "0.9.6")) == (12, 132, 37)


def test_cargo():
    output = get_version_diff_stats(
        CARGO,
        "guppy",
        "0.8.0",
        "0.9.0",
    )
    assert get_sha_stat(output) == (
        "d11084663f5c6757f0882f938a0c6a204996a1c4",
        "fe61a8b85feab1963ee1985bf0e4791fdd354aa5",
    )
    assert get_files_loc_stat(output) == (9, 222, 171)


def test_source_target_file():
    output = get_version_diff_stats(
        CARGO,
        "nix",
        "0.22.2",
        "0.23.0",
    )
    assert output.diff["CONVENTIONS.md"].target_file is None


def test_sanitize_repo_url():
    assert (
        sanitize_repo_url("https://github.com/nasifimtiazohi/version-differ/issues/1")
        == "https://github.com/nasifimtiazohi/version-differ"
    )
    assert (
        sanitize_repo_url("https://gitlab.com/gitlab-org/charts/gitlab/-/tree/master/doc/architecture")
        == "https://gitlab.com/gitlab-org/charts"
    )


def test_numpy():
    output = get_version_diff_stats(PIP, "numpy", "1.10.0", "1.21.5")
    print(output.diff.keys())
