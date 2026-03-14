from logging import root


def cleanup(input_path: str = "full_specs.json") -> str:
    """
    Reads the json file from spec_dummper, starts to save only the relevant info for the scanners to read.
    """
    ## TO DO

    try:
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(specs, f, indent=2, default=str)
        print_step_done(True)
        return output_path
    except Exception as e:
        print_step_done(False)
        print_error(f"Failed to save {output_path}: {e}")
        return ""

if __name__ == "__main__":
    out = cleanup()
    if out:
        print(f"Saved specs to {out}")
