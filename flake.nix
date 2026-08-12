{
  description = "Nicktoons Unite! (GCN) level-data reverse-engineering toolkit and web viewer";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }: let
    systems = [ "x86_64-linux" "aarch64-linux" ];
    forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);
  in {
    packages = forAllSystems (system: let
      pkgs = nixpkgs.legacyPackages.${system};
    in rec {
      # ISO -> viewer JSON. Pure build; the ISO is a runtime input only.
      extractor = pkgs.python3.pkgs.buildPythonApplication {
        pname = "nicku-extract";
        version = "0.1.0";
        format = "pyproject";
        src = ./extractor;
        nativeBuildInputs = [ pkgs.python3.pkgs.setuptools pkgs.makeWrapper ];
        # WIT (wiimms-iso-tools) is invoked at runtime to extract the ISO.
        postFixup = ''
          wrapProgram $out/bin/nicku-extract \
            --prefix PATH : ${pkgs.wiimms-iso-tools}/bin
        '';
        meta = {
          description = "Nicktoons Unite! ISO -> viewer JSON extraction toolkit";
          license = pkgs.lib.licenses.mit;
          mainProgram = "nicku-extract";
        };
      };

      # The static viewer (no generated data; run .#extract --out <dir> to fill
      # in collision/ and entities/, or use scripts/deploy-gh-pages.sh).
      viewer = pkgs.stdenv.mkDerivation {
        name = "nicku-viewer";
        src = ./viewer;
        installPhase = ''
          mkdir -p "$out"
          cp -r . "$out/"
        '';
        meta.description = "Static web viewer for Nicktoons Unite! levels";
      };

      default = extractor;
    });

    apps = forAllSystems (system: {
      extract = {
        type = "app";
        program = "${self.packages.${system}.extractor}/bin/nicku-extract";
      };
      default = self.apps.${system}.extract;
    });

    devShells = forAllSystems (system: let
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      default = pkgs.mkShell {
        name = "nicku-mapper";
        buildInputs = with pkgs; [
          # extraction
          (python3.withPackages (ps: [ ps.capstone ]))
          wiimms-iso-tools
          # web viewer / tests
          nodejs_22
          # DOL reverse-engineering (optional, heavy)
          ghidra
          # utilities
          file
          hexdump
          git-filter-repo   # history rewrites
        ];
        shellHook = ''
          echo "nicku-mapper dev shell"
          echo "  nix run .#extract -- --iso /path/nicktoonsunite.iso --out ./site"
          echo "  viewer: python3 -m http.server 8080 -d viewer"
        '';
      };
    });

    checks = forAllSystems (system: {
      # The extractor must build and its CLI must respond without an ISO.
      extractor-smoke = self.packages.${system}.extractor.overrideAttrs (old: {
        doInstallCheck = true;
        installCheckPhase = ''
          $out/bin/nicku-extract --help >/dev/null
        '';
      });
    });
  };
}
