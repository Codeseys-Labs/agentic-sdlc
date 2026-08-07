#!/usr/bin/env node
/* Parse and sanitize private raw SVG with the pinned browser DOM and CSSOM. */
import fs from "node:fs/promises";
import path from "node:path";

const [input, output, policyPath, executablePath] = process.argv.slice(2);
if (!input || !output || !policyPath || !executablePath || process.argv.length !== 6) {
  process.exitCode = 2;
} else {
  try {
    const [raw, policyText] = await Promise.all([fs.readFile(input, "utf8"), fs.readFile(policyPath, "utf8")]);
    const policy = JSON.parse(policyText);
    if (policy.schema_version !== "mermaid-renderer-linux/v1") throw new Error("unsupported policy schema");
    if (raw.length > policy.limits.max_raw_bytes) throw new Error("raw SVG exceeds policy limit");
    if (/<!DOCTYPE|<!ENTITY|<!\[CDATA\[/i.test(raw)) throw new Error("XML declarations are forbidden");
    if (/<(?:script|iframe|object|embed|foreignObject|animate(?:Color|Motion|Transform)?|set|discard|audio|video|image)\b|\son[a-z]+\s*=/i.test(raw)) {
      throw new Error("raw SVG has forbidden active or external content");
    }
    const puppeteer = (await import("puppeteer")).default;
    const browser = await puppeteer.launch({
      headless: "shell",
      executablePath,
      userDataDir: path.join(path.dirname(output), "profile"),
      args: ["--disable-background-networking", "--disable-component-update", "--disable-default-apps", "--disable-sync", "--metrics-recording-only", "--no-first-run"],
    });
    try {
      const serialized = await browser.newPage().then(async page => page.evaluate(({ value, p }) => {
        const rejected = message => { throw new Error(message); };
        const document = new DOMParser().parseFromString(value, "image/svg+xml");
        if (document.querySelector("parsererror")) rejected("browser XML parser rejected SVG");
        const svg = p.svg;
        const elements = new Set(svg.elements);
        const forbidden = new Set(svg.forbidden_elements);
        const attributes = new Set(svg.attributes);
        const uriAttributes = new Set(svg.uri_attributes);
        const cssProperties = new Set(svg.css_properties);
        const namespaces = new Set(Object.values(svg.namespaces));
        const unsafeUri = /(?:^|[^#])(?:javascript:|data:|file:|https?:|\/\/)/i;
        const unsafeCss = /@(?:import|namespace)|url\(\s*(?!['"]?#)[^)]|(?:behavior|expression)\s*:/i;
        const validateCss = text => {
          if (unsafeCss.test(text)) rejected("unsafe CSS rule");
          const sheet = new CSSStyleSheet();
          sheet.replaceSync(`x{${text}}`);
          for (const rule of sheet.cssRules) {
            if (rule.type === CSSRule.IMPORT_RULE || rule.type === CSSRule.NAMESPACE_RULE) rejected("unsafe CSSOM rule");
            if (rule.type === CSSRule.STYLE_RULE) for (const name of rule.style) if (!cssProperties.has(name) && !name.startsWith("--")) rejected(`unsafe CSS property ${name}`);
          }
        };
        for (const node of document.querySelectorAll("*")) {
          const local = node.localName;
          if (!namespaces.has(node.namespaceURI) || forbidden.has(local) || !elements.has(local)) rejected(`forbidden SVG node ${local}`);
          if (local === "style") validateCss(node.textContent || "");
          for (const attribute of node.attributes) {
            const key = attribute.namespaceURI === "http://www.w3.org/1999/xlink" && attribute.localName === "href" ? "xlink:href" : attribute.namespaceURI === "http://www.w3.org/2000/xmlns/" && attribute.localName === "xmlns" ? "xmlns" : attribute.namespaceURI === "http://www.w3.org/2000/xmlns/" ? `xmlns:${attribute.localName}` : attribute.localName;
            if (attribute.namespaceURI && attribute.namespaceURI !== "http://www.w3.org/2000/xmlns/" && !namespaces.has(attribute.namespaceURI)) rejected("forbidden attribute namespace");
            if (key.toLowerCase().startsWith("on") || !attributes.has(key)) rejected(`forbidden SVG attribute ${key}`);
            if (key === "style") validateCss(attribute.value);
            if (uriAttributes.has(key) && attribute.value.trim() && !(attribute.value.trim().startsWith("#") || attribute.value.trim().toLowerCase().startsWith("url(#"))) rejected(`non-fragment reference ${key}`);
            if (uriAttributes.has(key) && unsafeUri.test(attribute.value)) rejected(`unsafe reference ${key}`);
          }
        }
        return new XMLSerializer().serializeToString(document.documentElement);
      }, { value: raw, p: policy }));
      if (serialized.length > policy.limits.max_final_bytes) throw new Error("final SVG exceeds policy limit");
      await fs.writeFile(output, serialized, { encoding: "utf8", mode: 0o600, flag: "wx" });
    } finally {
      await browser.close();
    }
  } catch (error) {
    console.error(`mermaid-sanitizer: ${error.message}`);
    process.exitCode = 1;
  }
}
