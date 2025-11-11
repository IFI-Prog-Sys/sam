# shell.nix
# Pinned to latest commit @ 11.11.2025
let
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/1a091815c72c2d3231327923c8f8a60e81999169.tar.gz") {};
in pkgs.mkShell {
  packages = with pkgs; [
    (
    python3.withPackages (python-pkgs: with python-pkgs; [
      # Python packages here
    ]))
  ];
}
