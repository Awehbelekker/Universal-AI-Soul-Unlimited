/**
 * Copy the PWA from ../web into ./www for the Capacitor shell.
 */
import { cpSync, mkdirSync, rmSync, existsSync, writeFileSync, readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const web = join(root, "..", "web");
const www = join(root, "www");

if (!existsSync(web)) {
  console.error("Missing web/ folder at", web);
  process.exit(1);
}

rmSync(www, { recursive: true, force: true });
mkdirSync(www, { recursive: true });
cpSync(web, www, { recursive: true });

// Capacitor entry hint file (not required; index.html is the launch page)
writeFileSync(
  join(www, "capacitor-env.json"),
  JSON.stringify(
    {
      shell: "capacitor",
      note: "Set Brain URL in Settings to your PC serve_pwa address (LAN).",
    },
    null,
    2
  ),
  "utf8"
);

console.log("Synced web/ → mobile/www (", readFileSync(join(www, "index.html"), "utf8").length, "bytes index)");
