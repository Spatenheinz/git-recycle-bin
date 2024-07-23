{ pkgs ? import <nixpkgs> {} }:

pkgs.python311Packages.buildPythonApplication rec {
  pname = "git-recycle-bin";
  version = "0.2";

  src = ./.;
  format = "setuptools";

  propagatedBuildInputs = [ pkgs.git ] ++ pythonPath;

  pythonPath = with pkgs.python311Packages; [
    maya
    colorama
    pytest
  ];
}
