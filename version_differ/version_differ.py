"""Main module."""

from git.exc import CacheError
import requests
import json
import os
import sys
from zipfile import ZipFile
import tarfile
from pygit2 import init_repository, Signature
from time import time
import tempfile
from git import Repo
import re
from unidiff import PatchSet
from urllib.parse import urlparse, parse_qs
from os.path import join
import shutil

CARGO = "Cargo"
COMPOSER = "Composer"
GO = "Go"
MAVEN = "Maven"
NPM = "npm"
NUGET = "NuGet"
PYPI = PIP = "pip"
RUBYGEMS = "RubyGems"
ecosystems = [CARGO, COMPOSER, GO, MAVEN, NPM, NUGET, PYPI, RUBYGEMS]


class VersionDifferOutput:
    def __init__(self):
        self.old_version = None
        self.old_version_git_sha = None
        self.new_version = None
        self.new_version_git_sha = None
        self.diff = None

    def to_json(self):
        return {
            "metadata_info": {
                "old_version": self.old_version,
                "old_version_git_sha": self.old_version_git_sha,
                "new_version": self.new_version,
                "new_version_git_sha": self.new_version_git_sha,
            },
            "diff": self.diff,
        }


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
    patterns = [
        # 1. Ensure the version part does not follow any digit between 1-9,
        # e.g., to distinguish betn 0.1.8 vs 10.1.8
        r"^(?:.*[^1-9])?{}$".format(version_formatted_for_regex),
        # 2. If still more than one candidate,
        # check the extistence of crate name
        r"^.*{}(?:.*[^1-9])?{}$".format(package, version_formatted_for_regex),
        # 3. check if and only if crate name and version string is present
        # besides non-alphanumeric, e.g., to distinguish guppy vs guppy-summaries
        r"^.*{}\W*{}$".format(package, version_formatted_for_regex),
    ]

    for pattern in patterns:
        tags = list(filter(lambda tag: re.compile(pattern).match(tag.name.strip()), tags))
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
    temp_dir = tempfile.TemporaryDirectory()
    repo = Repo.clone_from(url, temp_dir.name)
    tags = repo.tags

    old_commit = get_commit_of_release(tags, package, old)
    new_commit = get_commit_of_release(tags, package, new)

    if old_commit and new_commit:

        output.old_version_git_sha = old_commit
        output.new_version_git_sha = new_commit
        output.diff = get_diff_stats(temp_dir.name, old_commit, new_commit)

    temp_dir.cleanup()
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

    return output.to_json()


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

    temp_dir_old = tempfile.TemporaryDirectory()
    url = get_package_version_source_url(ecosystem, package, old)
    if url:
        old_path = download_package_source(url, ecosystem, package, old, temp_dir_old.name)
        # currently only cargo provides git sha
        if ecosystem == CARGO:
            output.old_version_git_sha = get_git_sha_from_cargo_crate(old_path)
    else:
        return output

    temp_dir_new = tempfile.TemporaryDirectory()
    url = get_package_version_source_url(ecosystem, package, new)
    if url:
        new_path = download_package_source(url, ecosystem, package, new, temp_dir_new.name)
        # currently only cargo provides git sha
        if ecosystem == CARGO:
            output.new_version_git_sha = get_git_sha_from_cargo_crate(new_path)
    else:
        return output

    repo_old, oid_old = init_git_repo(old_path)
    repo_new, oid_new = init_git_repo(new_path)

    setup_remote(repo_old, new_path)

    output.diff = get_diff_stats(old_path, oid_old, oid_new)

    temp_dir_old.cleanup()
    temp_dir_new.cleanup()

    return output


def get_maven_pacakge_url(package):
    url = "https://repo1.maven.org/maven2/" + package.replace(".", "/").replace(":", "/")
    if requests.get(url).status_code == 200:
        return url

    s1, s2 = package.split(":")
    url = "https://repo1.maven.org/maven2/" + s1.replace(".", "/") + "/" + s2
    if requests.get(url).status_code == 200:
        return url


def download_zipped(url, path):
    compressed_file_name = "temp_data.zip"
    dest_file = "{}/{}".format(path, compressed_file_name)

    r = requests.get(url, stream=True)
    with open(dest_file, "wb") as output_file:
        output_file.write(r.content)

    z = ZipFile(dest_file, "r")
    z.extractall(path)
    z.close()

    os.remove(dest_file)


def download_tar(url, path):
    compressed_file_name = "temp_data.tar.gz"
    dest_file = "{}/{}".format(path, compressed_file_name)
    r = requests.get(url)
    with open(dest_file, "wb") as output_file:
        output_file.write(r.content)

    # TODO: can we make this logic a bit clearer
    flag = True
    while flag:
        flag = False
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith("tar.gz"):
                    filepath = "{}/{}".format(root, file)
                    try:
                        # extract the tar file and delete itself
                        t = tarfile.open(filepath)
                        t.extractall(path)
                        t.close()
                        os.remove(filepath)
                        flag = True
                    except:
                        # in npm, main tar extracts into data.tar.gz
                        if file == "temp_data.tar.gz" or file == "data.tar.gz":
                            raise Exception("cannot extract the main tar")
                        else:
                            # don't bother
                            pass


def download_package_source(url, ecosystem, package, version, dir_path):
    print("fetching {}-{} in {} ecosystem from {}".format(package, version, ecosystem, url))
    # First try based on file extension
    if url.endswith(".whl") or url.endswith(".jar") or url.endswith(".zip"):
        download_zipped(url, dir_path)
    elif url.endswith(".gz") or url.endswith(".crate") or url.endswith(".gem") or url.endswith(".tgz"):
        download_tar(url, dir_path)
    elif ecosystem == COMPOSER or ecosystem == MAVEN:
        download_zipped(url, dir_path)
    elif ecosystem == NPM or ecosystem == PYPI or ecosystem == RUBYGEMS or ecosystem == CARGO:
        download_tar(url, dir_path)
    else:
        # do nothing
        return None

    path = None
    if ecosystem == COMPOSER or ecosystem == NPM or ecosystem == CARGO:
        files = os.listdir(dir_path)
        assert len(files) == 1
        path = "{}/{}".format(dir_path, files[0])
    elif ecosystem == PIP:
        files = os.listdir(dir_path)
        if len(files) == 1:
            # for tar.gz extractions
            path = "{}/{}".format(dir_path, files[0])
        else:
            # assuming wheel file
            distinfo = None
            for f in files:
                if f.endswith(".dist-info"):
                    distinfo = f
                    break
            if distinfo:
                shutil.rmtree(join(dir_path, distinfo), ignore_errors=True)
                path = dir_path
    elif ecosystem == MAVEN:
        path = dir_path
    elif ecosystem == RUBYGEMS:
        files = os.listdir(dir_path)
        if len(files) == 1:
            path = "{}/{}".format(dir_path, files[0])
        else:
            path = dir_path
    else:
        files = os.listdir(dir_path)
        sys.exit("check downloding regstiry tarball for:{}-{}".format(ecosystem, files))
    assert path, "cannot extract {}-{}".format(ecosystem, package)
    return path


def get_package_version_source_url(ecosystem, package, version):
    assert ecosystem in ecosystems

    if ecosystem == CARGO:
        return "https://crates.io/api/v1/crates/{}/{}/download".format(package, version)
    elif ecosystem == COMPOSER:
        url = "https://repo.packagist.org/packages/{}.json".format(package)
        page = requests.get(url)
        data = json.loads(page.content)
        data = data["package"]["versions"]
        data = {k[1:] if k.startswith("v") else k: v for k, v in data.items()}
        if version in data:
            return data[version]["dist"]["url"]
    elif ecosystem == NPM:
        url = "https://registry.npmjs.org/{}".format(package)
        page = requests.get(url)
        data = json.loads(page.content)
        data = data["versions"]
        data = {k[1:] if k.startswith("v") else k: v for k, v in data.items()}
        if version in data:
            return data[version]["dist"]["tarball"]
    elif ecosystem == PYPI:
        url = "https://pypi.org/pypi/{}/json".format(package)
        page = requests.get(url)
        data = json.loads(page.content)
        data = data["releases"]
        data = {k[1:] if k.startswith("v") else k: v for k, v in data.items()}
        if version in data:
            data = data[version]
            url = next((x["url"] for x in data if x["url"].endswith(".whl")), data[-1]["url"])
            return url
    elif ecosystem == RUBYGEMS:
        return "https://rubygems.org/downloads/{}-{}.gem".format(package, version)
    elif ecosystem == MAVEN:
        url = get_maven_pacakge_url(package)
        if url:
            artifact = package.split(":")[1]
            url = "{}/{}/{}-{}-sources.jar".format(url, version, artifact, version)
            if requests.get(url).status_code == 200:
                return url


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


def get_diff_stats_from_git_diff(uni_diff_text):
    patch_set = PatchSet(uni_diff_text)

    files = {}

    for patched_file in patch_set:
        file_path = patched_file.path  # file name

        ad_line = [
            line.value for hunk in patched_file for line in hunk if line.is_added and line.value.strip() != ""
        ]  # the row number of deleted lines
        lines_added = len(ad_line)

        del_line = [
            line.value for hunk in patched_file for line in hunk if line.is_removed and line.value.strip() != ""
        ]  # the row number of added liens
        lines_removed = len(del_line)

        loc_change = lines_added + lines_removed
        if loc_change > 0:
            files[file_path] = {
                "loc_added": lines_added,
                "loc_removed": lines_removed,
                "added_lines": ad_line,
                "deleted_lines": del_line,
            }

    return files


def get_diff_stats(repo_path, commit_a, commit_b):
    repository = Repo(repo_path)

    uni_diff_text = repository.git.diff(str(commit_a), str(commit_b), ignore_blank_lines=True, ignore_space_at_eol=True)

    return get_diff_stats_from_git_diff(uni_diff_text)
