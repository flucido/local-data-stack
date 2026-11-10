use std::env;
use std::path::Path;

fn main() {
    let bundled = env::var("CARGO_FEATURE_BUNDLED_DUCKDB").is_ok();
    if cfg!(target_os = "macos") && !bundled {
        for candidate in ["/opt/homebrew/opt/duckdb/lib", "/opt/homebrew/lib", "/usr/local/lib"] {
            if Path::new(candidate).join("libduckdb.dylib").exists() {
                println!("cargo:rustc-link-search=native={candidate}");
                println!("cargo:rustc-link-arg=-Wl,-rpath,{candidate}");
                break;
            }
        }
    }
}
