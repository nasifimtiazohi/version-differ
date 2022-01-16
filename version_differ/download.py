from version_differ.common import *
import requests
import json
import os
import sys
from zipfile import ZipFile
import tarfile
from os.path import join
import shutil


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
    elif ecosystem == MAVEN or ecosystem == RUBYGEMS:
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
        data = json.loads(requests.get(url).content)["package"]["versions"]
        data = {k[1:] if k.startswith("v") else k: v for k, v in data.items()}
        if version in data:
            return data[version]["dist"]["url"]
    elif ecosystem == NPM:
        url = "https://registry.npmjs.org/{}".format(package)
        data = json.loads(requests.get(url).content)["versions"]
        data = {k[1:] if k.startswith("v") else k: v for k, v in data.items()}
        if version in data:
            return data[version]["dist"]["tarball"]
    elif ecosystem == PYPI:
        url = "https://pypi.org/pypi/{}/json".format(package)
        data = json.loads(requests.get(url).content)["releases"]
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

    return None


def download_zipped(url, path):
    compressed_file_name = "temp_data.zip"
    dest_file = join(path, compressed_file_name)

    r = requests.get(url, stream=True)
    with open(dest_file, "wb") as output_file:
        output_file.write(r.content)

    z = ZipFile(dest_file, "r")
    z.extractall(path)
    z.close()
    os.remove(dest_file)


def download_tar(url, path):
    compressed_file_name = "temp_data.tar.gz"
    dest_file = join(path, compressed_file_name)

    r = requests.get(url)
    with open(dest_file, "wb") as output_file:
        output_file.write(r.content)

    t = tarfile.open(dest_file)
    t.extractall(path)
    t.close()
    os.remove(dest_file)

    # additional logic for ruby gems
    if url.endswith(".gem"):
        ruby_tar = "data.tar.gz"
        assert ruby_tar in os.listdir(path)
        ruby_tar = join(path, ruby_tar)

        t = tarfile.open(ruby_tar)
        t.extractall(path)
        t.close()
        os.remove(ruby_tar)

        for gz_file in [
            "metadata.gz",
            "checksums.yaml.gz",
            "data.tar.gz.sig",
            "metadata.gz.sig",
            "checksums.yaml.gz.sig",
        ]:
            if gz_file in os.listdir(path):
                os.remove(join(path, gz_file))


def get_maven_pacakge_url(package):
    url = "https://repo1.maven.org/maven2/" + package.replace(".", "/").replace(":", "/")
    if requests.get(url).status_code == 200:
        return url

    s1, s2 = package.split(":")
    url = "https://repo1.maven.org/maven2/" + s1.replace(".", "/") + "/" + s2
    if requests.get(url).status_code == 200:
        return url
