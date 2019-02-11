{ nixpkgs ? import <nixpkgs> {} }:

with nixpkgs;
with lib;

let

  python = python37;
  pythonPackages = python37Packages;
  virtualenv = pythonPackages.virtualenv;
  venv = ".venv";

  mkPythonPath = libs: makeSearchPathOutput "lib" python.sitePackages libs;

  pythonEnv = python.buildEnv.override {
    extraLibs = with pythonPackages; [
      jedi # IDE support on Emacs
    ];
  };

in

mkShell {
  name = "vialer-middleware";

  buildInputs = [
    pythonEnv
    virtualenv
    mysql55
    libffi
    openssl
    zlib
  ];

  shellHook = ''
    set -eo pipefail

    # direnv don't like no output on stdout.
    {
      if [ ! -d "${venv}" ]; then
         ${virtualenv}/bin/virtualenv -p ${python}/bin/python ${venv}
      fi

      source ${venv}/bin/activate
    } 1>&2

    export PYTHONPATH="$PYTHONPATH:${mkPythonPath [venv]}"

    # nix-shell sets this to 1.
    # Python does not accept the date to be before 1980.
    export SOURCE_DATE_EPOCH=$(date +%s)
  '';
}
