/* Runs the book's standard-library examples in a Pyodide sandbox. */
const PYODIDE_VERSION = "0.27.2";
const PYODIDE_BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

let bootPromise = null;
let pyodide = null;
let mounted = new Set();

async function boot() {
  if (bootPromise) return bootPromise;
  bootPromise = (async () => {
    importScripts(`${PYODIDE_BASE}pyodide.js`);
    pyodide = await loadPyodide({ indexURL: PYODIDE_BASE });
    pyodide.FS.mkdirTree("/project/examples");
    pyodide.FS.mkdirTree("/project/data/story");
    return pyodide;
  })();
  return bootPromise;
}

async function mountFiles(files) {
  const py = await boot();
  for (const file of files || []) {
    if (mounted.has(file.path)) continue;
    const directory = file.path.split("/").slice(0, -1).join("/");
    if (directory) py.FS.mkdirTree(directory);
    py.FS.writeFile(file.path, new TextEncoder().encode(file.content));
    mounted.add(file.path);
  }
}

self.onmessage = async (event) => {
  const { id, code, files, filename, argv } = event.data || {};
  let output = "";
  try {
    self.postMessage({ id, status: "booting" });
    const py = await boot();
    await mountFiles(files);
    self.postMessage({ id, status: "running" });

    py.setStdout({ batched: (text) => { output += text + "\n"; } });
    py.setStderr({ batched: (text) => { output += text + "\n"; } });
    await py.runPythonAsync(`import os, sys\nos.chdir('/project')\nsys.argv = ${JSON.stringify(argv || [])}`);

    const globals = py.toPy({
      __name__: "__main__",
      __file__: filename || "/project/examples/script.py",
    });
    await py.runPythonAsync(code, { globals });
    self.postMessage({ id, ok: true, output });
  } catch (error) {
    self.postMessage({
      id,
      ok: false,
      output: `${output}\n${error?.message || String(error)}`.trim(),
    });
  }
};
