{
  description = "Nicktoons Unite! level-data reverse-engineering toolkit";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
  in {
    devShells.${system}.default = pkgs.mkShell {
      name = "nicku-mapper";

      buildInputs = with pkgs; [
        # Python analysis / extraction
        (python3.withPackages (ps: with ps; [
          capstone          # PPC disassembly (dol.py, doldis.py)
        ]))

        # Web viewer
        nodejs_22

        # DOL reverse-engineering (optional, heavy)
        ghidra

        # Utilities
        file
        hexdump
      ];

      shellHook = ''
        echo "nicku-mapper dev shell"
        echo "  asset-extract/tools/trb_mesh.py  — mesh + collision extraction"
        echo "  scripts/dol/                     — DOL disassembly tools"
        echo "  web/                             — serve: python3 -m http.server 8080 -d web"
      '';
    };
  };
}
