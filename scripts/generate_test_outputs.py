from notebook_graph_outputs import ROOT_DIR, TESTS_DIR, clear_outputs, generate_graph_outputs


def main():
    clear_outputs()

    for notebook_path in sorted(TESTS_DIR.glob("*.ipynb")):
        dot_path, json_path, png_path = generate_graph_outputs(notebook_path)
        print(f"  DOT:  {dot_path.relative_to(ROOT_DIR)}")
        print(f"  JSON: {json_path.relative_to(ROOT_DIR)}")
        print(f"  PNG:  {png_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
