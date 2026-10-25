// Parse before CommonMark turns \( and \[ into ordinary escaped punctuation.
// A syntax extension leaves code, link destinations and existing $ math alone.
export function remarkLatexMath() {
  const data = this.data();
  (data.micromarkExtensions ||= []).push({
    text: { 92: { name: "latexMathText", tokenize: tokenizer(false) } },
    flow: { 92: { name: "latexMathFlow", concrete: true, tokenize: tokenizer(true) } },
  });
  (data.fromMarkdownExtensions ||= []).push({
    enter: {
      latexMath(token) {
        const display = this.sliceSerialize(token).startsWith("\\[");
        this.enter({
          type: display ? "math" : "inlineMath",
          value: "",
          data: {
            hName: "code",
            hProperties: { className: ["language-math", display ? "math-display" : "math-inline"] },
            hChildren: [],
          },
        }, token);
      },
    },
    exit: {
      latexMath(token) {
        const node = this.stack[this.stack.length - 1];
        node.value = this.sliceSerialize(token).slice(2, -2).trim();
        node.data.hChildren.push({ type: "text", value: node.value });
        this.exit(token);
      },
    },
  });
}

function tokenizer(flow) {
  return function (effects, ok, nok) {
    let close;
    let dataOpen = false;
    return start;

    function start(code) {
      effects.enter("latexMath");
      consume(code); // Backslash.
      return opening;
    }

    function opening(code) {
      if (code !== 91 && (flow || code !== 40)) return nok(code);
      close = code === 91 ? 93 : 41;
      consume(code);
      return inside;
    }

    function inside(code) {
      if (code === null) return nok(code); // Incomplete streamed formulas stay text.
      consume(code);
      return code === 92 ? escaped : inside;
    }

    function escaped(code) {
      if (code === null) return nok(code);
      consume(code);
      if (code !== close) return inside; // Includes \\: do not close on an escaped backslash.
      effects.exit("latexMathData");
      effects.exit("latexMath");
      return flow ? after : ok;
    }

    function consume(code) {
      // Keep each line in its own token: micromark uses these boundaries when
      // joining chunks from paragraphs, lists and blockquotes.
      if (code === -5 || code === -4 || code === -3) {
        if (dataOpen) effects.exit("latexMathData");
        dataOpen = false;
        effects.enter("lineEnding");
        effects.consume(code);
        effects.exit("lineEnding");
      } else {
        if (!dataOpen) effects.enter("latexMathData");
        dataOpen = true;
        effects.consume(code);
      }
    }

    function after(code) {
      // A flow block must occupy the rest of its line; otherwise use text parsing.
      if (code === null || code === -5 || code === -4 || code === -3) return ok(code);
      if (code !== 32 && code !== -2 && code !== -1) return nok(code);
      effects.enter("whitespace");
      effects.consume(code);
      effects.exit("whitespace");
      return after;
    }
  };
}
