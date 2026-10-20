// Vite plugin: stamps every HTML element written in the repo's own JSX with
// data-cypher-src="<repo path>:<line>", so a click on the rendered page can be traced back
// to the line of code that produced it. Only adds attributes; never changes behavior.
import path from "node:path";
import { transformAsync } from "@babel/core";
import syntaxJsx from "@babel/plugin-syntax-jsx";
import syntaxTypescript from "@babel/plugin-syntax-typescript";

export function sourceTags({ appRoot, repoPrefix }) {
  return {
    name: "cypher-source-tags",
    enforce: "pre",
    async transform(code, id) {
      const file = id.split("?")[0];
      if (!/\.[jt]sx$/.test(file) || file.includes("/node_modules/") || file.includes("/.cr-harness/")) return null;
      if (!file.startsWith(appRoot + path.sep)) return null;
      const repoPath = path.posix.join(repoPrefix, path.relative(appRoot, file).split(path.sep).join("/"));
      const result = await transformAsync(code, {
        filename: file,
        babelrc: false,
        configFile: false,
        sourceMaps: true,
        plugins: [
          syntaxJsx,
          ...(file.endsWith(".tsx") ? [syntaxTypescript] : []),
          ({ types: t }) => ({
            visitor: {
              JSXOpeningElement(p) {
                const name = p.node.name;
                // Lowercase tags are real DOM elements; components get tagged in their own file.
                if (name.type !== "JSXIdentifier" || !/^[a-z]/.test(name.name) || !p.node.loc) return;
                p.node.attributes.push(
                  t.jsxAttribute(
                    t.jsxIdentifier("data-cypher-src"),
                    t.stringLiteral(`${repoPath}:${p.node.loc.start.line}`),
                  ),
                );
              },
            },
          }),
        ],
      });
      return result && { code: result.code, map: result.map };
    },
  };
}
