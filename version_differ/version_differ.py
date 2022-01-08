"""Main module."""

import json
from pygit2 import init_repository, Signature
from time import time
import tempfile
from git import Repo
import re
from unidiff import PatchSet
from urllib.parse import urlparse, parse_qs
from os.path import join, relpath
import os
from version_differ.download import download_package_source, get_package_version_source_url
from version_differ.common import *


class VersionDifferOutput:
    def __init__(self):
        self.old_version = None
        self.old_version_git_sha = None
        self.new_version = None
        self.new_version_git_sha = None

        self.diff = None

        self.new_version_filelist = None
        self.old_version_filelist = None

    def to_json(self):
        return {
            "metadata_info": {
                "old_version": self.old_version,
                "old_version_git_sha": self.old_version_git_sha,
                "new_version": self.new_version,
                "new_version_git_sha": self.new_version_git_sha,
            },
            "diff": self.diff,
            "new_version_filelist": self.new_version_filelist,
            "old_version_filelist": self.old_version_filelist,
        }


class FileDiff:
    def __init__(self, source_file, target_file, is_rename, loc_added, loc_removed, added_lines, removed_lines):
        self.source_file = source_file
        self.target_file = target_file
        self.is_rename = is_rename
        self.loc_added = loc_added
        self.loc_removed = loc_removed
        self.added_lines = added_lines
        self.removed_lines = removed_lines

    # TODO: convert to json for cli output


def sanitize_repo_url(repo_url):
    parsed_url = urlparse(repo_url)
    host = parsed_url.netloc

    if host == "gitbox.apache.org" and "p" in parse_qs(parsed_url.query).keys():
        project_name = parse_qs(parsed_url.query)["p"]
        return "https://gitbox.apache.org/repos/asf/{}".format(project_name)

    if host == "svn.opensymphony.com":
        return repo_url

    # below rule covers github, gitlab, bitbucket, foocode, eday, qt
    sources = ["github", "gitlab", "bitbucket", "foocode", "eday", "q", "opendev"]
    assert any([x in host for x in sources]), "unknown host for repository url: {}".format(repo_url)

    paths = [s.removesuffix(".git") for s in parsed_url.path.split("/")]
    owner, repo = paths[1], paths[2]
    return "https://{}/{}/{}".format(host, owner, repo)


def get_commit_of_release(tags, package, version):
    """
    tags: gitpython object,
    version: string, taken from ecosystem data
    """

    # Now we check through a series of heuristics if tag matches a version
    version_formatted_for_regex = version.strip().replace(".", "\\.")
    package = package.lower()
    patterns = [
        # 1. Ensure the version part does not follow any digit between 1-9,
        # e.g., to distinguish betn 0.1.8 vs 10.1.8
        r"^(?:.*[^1-9])?{}$".format(version_formatted_for_regex),
        # 2. check if and only if crate name and version string is present
        # besides non-alphanumeric, e.g., to distinguish guppy vs guppy-summaries
        r"^.*{}\W*v?\W*{}$".format(package, version_formatted_for_regex),
    ]

    for pattern in patterns:
        tags = list(filter(lambda tag: re.compile(pattern).match(tag.name.strip().lower()), tags))
        if len(tags) == 1:
            return tags[0].commit


def get_go_module_path(package):
    """assumption: package name starts with <host>/org/repo"""
    return "/".join(package.split("/")[3:])


def get_version_diff_stats_from_repository_tags(package, repo_url, old, new):
    output = VersionDifferOutput()
    output.old_version = old
    output.new_version = new

    url = sanitize_repo_url(repo_url)
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Repo.clone_from(url, temp_dir)
        tags = repo.tags

        old_commit = get_commit_of_release(tags, package, old)
        new_commit = get_commit_of_release(tags, package, new)

        if old_commit and new_commit:

            output.old_version_git_sha = old_commit
            output.new_version_git_sha = new_commit
            output.diff = get_diff_stats(temp_dir, old_commit, new_commit)

            output.new_version_filelist = get_repository_file_list(temp_dir, new_commit)
            output.old_version_filelist = get_repository_file_list(temp_dir, old_commit)

    return output


def filter_go_package_files(package, files):
    module_path = get_go_module_path(package)
    if module_path:
        files = {k: v for (k, v) in files.items() if k.startswith(module_path)}
    return files


def filter_nuget_package_files(package, files):
    package = package.lower()
    subpath = None
    for file in files.keys():
        file = file.lower().split("/")
        if package in file:
            subpath = package
            break
        else:
            for path in file:
                if package.endswith(path):
                    temp = package[: -len(path)]
                    if temp[-1] == ".":
                        subpath = path
                        break
    if subpath:
        files = dict(filter(lambda x: subpath in x[0].lower().split("/"), files.items()))

    return files


def get_version_diff_stats(ecosystem, package, old, new, repo_url=None):
    if ecosystem == GO:
        assert repo_url, "Repository URL required for Go packages"
        output = get_version_diff_stats_from_repository_tags(package, repo_url, old, new)
        output.diff = filter_go_package_files(package, output.diff)
    elif ecosystem == NUGET:
        assert repo_url, "Repository URL required for NuGet packages"
        output = get_version_diff_stats_from_repository_tags(package, repo_url, old, new)
        output.diff = filter_nuget_package_files(package, output.diff)
    else:
        output = get_version_diff_stats_registry(ecosystem, package, old, new)

    return output


def get_git_sha_from_cargo_crate(package_path):
    try:
        with open(join(package_path, ".cargo_vcs_info.json"), "r") as f:
            data = json.load(f)
            return data["git"]["sha1"]
    except:
        return None


def get_version_diff_stats_registry(ecosystem, package, old, new):
    output = VersionDifferOutput()
    output.old_version = old
    output.new_version = new

    with tempfile.TemporaryDirectory() as temp_dir_old, tempfile.TemporaryDirectory() as temp_dir_new:
        url = get_package_version_source_url(ecosystem, package, old)
        if url:
            old_path = download_package_source(url, ecosystem, package, old, temp_dir_old)
            # currently only cargo provides git sha
            if ecosystem == CARGO:
                output.old_version_git_sha = get_git_sha_from_cargo_crate(old_path)
        else:
            return output

        url = get_package_version_source_url(ecosystem, package, new)
        if url:
            new_path = download_package_source(url, ecosystem, package, new, temp_dir_new)
            # currently only cargo provides git sha
            if ecosystem == CARGO:
                output.new_version_git_sha = get_git_sha_from_cargo_crate(new_path)
        else:
            return output

        repo_old, oid_old = init_git_repo(old_path)
        repo_new, oid_new = init_git_repo(new_path)

        setup_remote(repo_old, new_path)

        output.diff = get_diff_stats(old_path, oid_old, oid_new)

        output.new_version_filelist = get_repository_file_list(new_path, oid_new)
        output.old_version_filelist = get_repository_file_list(old_path, oid_old)

    return output


def init_git_repo(path):
    repo = init_repository(path)
    index = repo.index
    index.add_all()
    tree = index.write_tree()
    sig1 = Signature("user", "email@domain.com", int(time()), 0)
    oid = repo.create_commit("refs/heads/master", sig1, sig1, "Initial commit", tree, [])
    return repo, oid


def setup_remote(repo, url):
    remote_name = "remote"
    repo.create_remote(remote_name, url)
    remote = repo.remotes[remote_name]
    remote.connect()
    remote.fetch()


def process_patch_filepath(filepath):
    filepath = filepath.removeprefix("a/")
    filepath = filepath.removeprefix("b/")
    if filepath == "/dev/null":
        filepath = None
    return filepath


def get_diff_stats_from_git_diff(uni_diff_text):
    patch_set = PatchSet(uni_diff_text)

    files = {}

    for patched_file in patch_set:
        file_path = patched_file.path  # file name

        ad_lines = [
            line.value for hunk in patched_file for line in hunk if line.is_added and line.value.strip() != ""
        ]  # the row number of deleted lines
        lines_added = len(ad_lines)

        del_lines = [
            line.value for hunk in patched_file for line in hunk if line.is_removed and line.value.strip() != ""
        ]  # the row number of added liens
        lines_removed = len(del_lines)

        if lines_added + lines_removed > 0:
            files[file_path] = FileDiff(
                process_patch_filepath(patched_file.source_file),
                process_patch_filepath(patched_file.target_file),
                patched_file.is_rename,
                lines_added,
                lines_removed,
                ad_lines,
                del_lines,
            )

    return files


def get_diff_stats(repo_path, commit_a, commit_b):
    repository = Repo(repo_path)

    uni_diff_text = repository.git.diff(str(commit_a), str(commit_b), ignore_blank_lines=True, ignore_space_at_eol=True)

    return get_diff_stats_from_git_diff(uni_diff_text)


def get_repository_file_list(repo_path, commit):
    repo = Repo(repo_path)
    head = repo.head.object.hexsha

    repo.git.checkout(commit, force=True)
    filelist = []
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if not relpath(root, repo_path).startswith(".git"):
                filelist.append(relpath(join(root, file), repo_path))

    repo.git.checkout(head, force=True)
    return set(filelist)
