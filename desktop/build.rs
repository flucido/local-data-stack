use std::env;
use std::path::Path;

fn main() {
    let bundled = env::var("CARGO_FEATURE_BUNDLED_DUCKDB").is_ok();
    if !bundled {
        for candidate in ["/opt/homebrew/opt/duckdb/lib", "/opt/homebrew/lib", "/usr/local/lib"] {
            if Path::new(candidate).join("libduckdb.dylib").exists()
                || Path::new(candidate).join("libduckdb.so").exists()
            {
                println!("cargo:rustc-link-search=native={candidate}");
                println!("cargo:rustc-link-arg=-Wl,-rpath,{candidate}");
                break;
            }
        }
    }
}
