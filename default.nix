{ pkgs ? import <nixpkgs> {} }:

pkgs.python311Packages.buildPythonApplication rec {
  pname = "git-recycle-bin";
  version = "0.2.5";

  src = ./.;
  format = "setuptools";

  propagatedBuildInputs = [ pkgs.git ] ++ pythonPath;

  pythonPath = with pkgs.python311Packages; [
    maya
    colorama
    dateparser
    pytest
  ];

  postInstall = ''
    install -Dm755 ${./aux/git_add_ssh_remote.sh} $out/bin/git_add_ssh_remote.sh
  '';
}
