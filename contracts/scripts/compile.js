// Compile all contracts with solc-js (no network, no Hardhat needed) and write ABIs for the Python SDK.
// Usage: npm install solc@0.8.26 && node scripts/compile.js [--bytecode out.json]
const fs = require("fs"), path = require("path");
const solc = require("solc");
const root = path.join(__dirname, "..");
const files = ["Owned2Step.sol", "CateryaAnchorRegistry.sol", "CateryaAssuranceGate.sol", "CateryaEvaluatorBond.sol",
  "interfaces/ICateryaAssuranceGate.sol", "examples/AssuranceGatedPool.sol"];
const sources = Object.fromEntries(files.map(f => [f, { content: fs.readFileSync(path.join(root, f), "utf8") }]));
const input = { language: "Solidity", sources, settings: { optimizer: { enabled: true, runs: 200 }, outputSelection: { "*": { "*": ["abi", "evm.bytecode.object"] } } } };
const out = JSON.parse(solc.compile(JSON.stringify(input), { import: p => {
  const f = path.join(root, p); return fs.existsSync(f) ? { contents: fs.readFileSync(f, "utf8") } : { error: "not found: " + p }; } }));
let bad = false;
for (const e of out.errors || []) { console.error(e.formattedMessage); if (e.severity === "error") bad = true; }
if (bad) process.exit(1);
const abiDir = path.join(root, "..", "src", "caterya", "blockchain", "abi");
fs.mkdirSync(abiDir, { recursive: true });
const bc = {};
for (const [file, contracts] of Object.entries(out.contracts)) for (const [name, c] of Object.entries(contracts)) {
  if (name === "Owned2Step") continue;
  fs.writeFileSync(path.join(abiDir, name + ".json"), JSON.stringify(c.abi, null, 2) + "\n");
  bc[name] = { abi: c.abi, bytecode: "0x" + c.evm.bytecode.object };
  console.log("compiled", name, "bytecode bytes:", c.evm.bytecode.object.length / 2);
}
const i = process.argv.indexOf("--bytecode");
if (i > 0) fs.writeFileSync(process.argv[i + 1], JSON.stringify(bc));
