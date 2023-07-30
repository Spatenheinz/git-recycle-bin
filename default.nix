{ pkgs ? import <nixpkgs> {} }:

pkgs.python39Packages.buildPythonApplication rec {
  pname = "git-recycle-bin";
  version = "0.2";

  src = ./.;
  format = "setuptools";

  propagatedBuildInputs = [ pkgs.git ] ++ pythonPath;

  pythonPath = with pkgs.python39Packages; [
    maya
    colorama
    pytest
  ];
}
