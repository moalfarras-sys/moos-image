// MoOS Search Instant Answers Engine: Safe Math & Unit/Currency Converter.
// Strictly tokenized, zero eval, zero code execution.
.pragma library

// ── Unit conversion rates relative to standard base ─────────────────────────
const LENGTH = {
    "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
    "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
    "m": 1.0, "meter": 1.0, "meters": 1.0,
    "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
    "mi": 1609.344, "mile": 1609.344, "miles": 1609.344
};

const MASS = {
    "mg": 0.000001, "milligram": 0.000001, "milligrams": 0.000001,
    "g": 0.001, "gram": 0.001, "grams": 0.001,
    "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "t": 1000.0, "tonne": 1000.0, "ton": 1000.0, "tons": 1000.0,
    "oz": 0.02834952, "ounce": 0.02834952, "ounces": 0.02834952,
    "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237, "pounds": 0.45359237
};

const DATA = {
    "b": 1, "byte": 1, "bytes": 1,
    "kb": 1024, "kilobyte": 1024, "kilobytes": 1024,
    "mb": 1048576, "megabyte": 1048576, "megabytes": 1048576,
    "gb": 1073741824, "gigabyte": 1073741824, "gigabytes": 1073741824,
    "tb": 1099511627776, "terabyte": 1099511627776, "terabytes": 1099511627776
};

const TIME = {
    "ms": 0.001, "millisecond": 0.001, "milliseconds": 0.001,
    "s": 1, "sec": 1, "second": 1, "seconds": 1,
    "min": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
    "w": 604800, "week": 604800, "weeks": 604800
};

// Benchmark base reference rates to USD
const CURRENCY = {
    "usd": 1.0, "dollar": 1.0, "dollars": 1.0,
    "eur": 1.08, "euro": 1.08, "euros": 1.08,
    "gbp": 1.28, "pound": 1.28, "pounds": 1.28,
    "sar": 0.2666, "riyal": 0.2666, "riyals": 0.2666,
    "aed": 0.2723, "dirham": 0.2723, "dirhams": 0.2723,
    "jpy": 0.0068, "yen": 0.0068,
    "egp": 0.0207,
    "cad": 0.74,
    "aud": 0.66,
    "chf": 1.13,
    "cny": 0.14
};

function formatNumber(num) {
    if (isNaN(num) || !isFinite(num)) return null;
    if (Math.abs(num) >= 1e12 || (Math.abs(num) < 1e-4 && num !== 0)) {
        return num.toExponential(4);
    }
    const rounded = Math.round(num * 10000) / 10000;
    return rounded.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

// ── Unit Conversion ─────────────────────────────────────────────────────────
function tryUnitConversion(query) {
    const q = query.trim().toLowerCase();
    // Patterns: "100 km to miles", "50 c in f", "100 eur to usd", "1024 mb in gb"
    const match = q.match(/^([+-]?[0-9]+(?:\.[0-9]+)?)\s*([a-z°]+)\s+(?:to|in|into)\s+([a-z°]+)$/);
    if (!match) return null;

    const val = parseFloat(match[1]);
    const fromUnit = match[2].replace("°", "");
    const toUnit = match[3].replace("°", "");

    // Temperature conversion
    if ((fromUnit === "c" || fromUnit === "celsius") && (toUnit === "f" || toUnit === "fahrenheit")) {
        const res = (val * 9 / 5) + 32;
        const formatted = (Math.round(res * 100) / 100) + " °F";
        return {
            valid: true,
            type: "unit",
            expression: val + " °C = " + formatNumber(res) + " °F",
            result: String(Math.round(res * 100) / 100),
            formattedResult: formatted,
            value: formatted
        };
    }
    if ((fromUnit === "f" || fromUnit === "fahrenheit") && (toUnit === "c" || toUnit === "celsius")) {
        const res = (val - 32) * 5 / 9;
        const formatted = (Math.round(res * 100) / 100) + " °C";
        return {
            valid: true,
            type: "unit",
            expression: val + " °F = " + formatNumber(res) + " °C",
            result: String(Math.round(res * 100) / 100),
            formattedResult: formatted,
            value: formatted
        };
    }
    if ((fromUnit === "c" || fromUnit === "celsius") && (toUnit === "k" || toUnit === "kelvin")) {
        const res = val + 273.15;
        const formatted = (Math.round(res * 100) / 100) + " K";
        return {
            valid: true,
            type: "unit",
            expression: val + " °C = " + formatNumber(res) + " K",
            result: String(Math.round(res * 100) / 100),
            formattedResult: formatted,
            value: formatted
        };
    }
    if ((fromUnit === "k" || fromUnit === "kelvin") && (toUnit === "c" || toUnit === "celsius")) {
        const res = val - 273.15;
        const formatted = (Math.round(res * 100) / 100) + " °C";
        return {
            valid: true,
            type: "unit",
            expression: val + " K = " + formatNumber(res) + " °C",
            result: String(Math.round(res * 100) / 100),
            formattedResult: formatted,
            value: formatted
        };
    }

    // Standard tables check
    const tables = [LENGTH, MASS, DATA, TIME, CURRENCY];
    for (let i = 0; i < tables.length; ++i) {
        const tbl = tables[i];
        if (fromUnit in tbl && toUnit in tbl) {
            const baseVal = val * tbl[fromUnit];
            const converted = baseVal / tbl[toUnit];
            const isCurr = (tbl === CURRENCY);
            const unitLabel = toUnit.toUpperCase();
            return {
                valid: true,
                type: isCurr ? "currency" : "unit",
                expression: val + " " + fromUnit + " = " + formatNumber(converted) + " " + toUnit,
                result: String(Math.round(converted * 10000) / 10000),
                formattedResult: formatNumber(converted) + " " + (isCurr ? unitLabel : toUnit),
                value: formatNumber(converted) + " " + (isCurr ? unitLabel : toUnit)
            };
        }
    }

    return null;
}

// ── Safe Math Parser ────────────────────────────────────────────────────────
function tokenizeMath(expr) {
    const tokens = [];
    let i = 0;
    const s = expr.replace(/\s+/g, "");

    while (i < s.length) {
        const c = s[i];

        // Numbers (including decimals)
        if ((c >= "0" && c <= "9") || c === ".") {
            let num = "";
            while (i < s.length && ((s[i] >= "0" && s[i] <= "9") || s[i] === ".")) {
                num += s[i++];
            }
            tokens.push({ type: "NUMBER", value: parseFloat(num) });
            continue;
        }

        // Operators
        if (c === "+" || c === "-" || c === "*" || c === "/" || c === "^" || c === "%" || c === "(" || c === ")") {
            tokens.push({ type: "OP", value: c });
            i++;
            continue;
        }

        // Functions or constants (sqrt, sin, cos, tan, abs, log, ln, pi, e)
        if (c >= "a" && c <= "z") {
            let ident = "";
            while (i < s.length && s[i] >= "a" && s[i] <= "z") {
                ident += s[i++];
            }
            if (ident === "pi") {
                tokens.push({ type: "NUMBER", value: Math.PI });
            } else if (ident === "e") {
                tokens.push({ type: "NUMBER", value: Math.E });
            } else if (["sqrt", "sin", "cos", "tan", "abs", "round", "floor", "ceil", "log", "ln", "exp"].indexOf(ident) >= 0) {
                tokens.push({ type: "FUNC", value: ident });
            } else if (ident === "of") {
                tokens.push({ type: "OP", value: "*" });
            } else {
                return null; // Unknown identifier
            }
            continue;
        }

        return null; // Unknown character
    }
    return tokens;
}

function parseTokens(tokens) {
    if (!tokens || tokens.length === 0) return null;

    let pos = 0;

    function peek() {
        return pos < tokens.length ? tokens[pos] : null;
    }

    function consume(expectedVal) {
        const t = peek();
        if (!t) return null;
        if (expectedVal !== undefined && t.value !== expectedVal) return null;
        pos++;
        return t;
    }

    // Grammar:
    // Expr -> Term ((+ | -) Term)*
    // Term -> Power ((* | / | %) Power)*
    // Power -> Factor (^ Power)?
    // Factor -> (+ | -)? Primary
    // Primary -> NUMBER | FUNC ( Expr ) | ( Expr )

    function parseExpr() {
        let left = parseTerm();
        if (left === null) return null;

        while (true) {
            const next = peek();
            if (next && next.type === "OP" && (next.value === "+" || next.value === "-")) {
                consume();
                const right = parseTerm();
                if (right === null) return null;
                left = (next.value === "+") ? (left + right) : (left - right);
            } else {
                break;
            }
        }
        return left;
    }

    function parseTerm() {
        let left = parsePower();
        if (left === null) return null;

        while (true) {
            const next = peek();
            if (next && next.type === "OP" && (next.value === "*" || next.value === "/" || next.value === "%")) {
                consume();
                const right = parsePower();
                if (right === null) return null;
                if (next.value === "*") left = left * right;
                else if (next.value === "/") {
                    if (right === 0) return null; // Div by zero
                    left = left / right;
                } else if (next.value === "%") {
                    left = left % right;
                }
            } else {
                break;
            }
        }
        return left;
    }

    function parsePower() {
        const base = parseFactor();
        if (base === null) return null;

        const next = peek();
        if (next && next.type === "OP" && next.value === "^") {
            consume();
            const exponent = parsePower(); // right-associative
            if (exponent === null) return null;
            return Math.pow(base, exponent);
        }
        return base;
    }

    function parseFactor() {
        const next = peek();
        if (next && next.type === "OP" && (next.value === "+" || next.value === "-")) {
            consume();
            const val = parsePrimary();
            if (val === null) return null;
            return (next.value === "-") ? -val : val;
        }
        return parsePrimary();
    }

    function parsePrimary() {
        const t = peek();
        if (!t) return null;

        if (t.type === "NUMBER") {
            consume();
            // Check for trailing percentage (e.g. 15%)
            const p = peek();
            if (p && p.type === "OP" && p.value === "%") {
                consume();
                return t.value / 100;
            }
            return t.value;
        }

        if (t.type === "FUNC") {
            consume();
            if (!consume("(")) return null;
            const arg = parseExpr();
            if (arg === null || !consume(")")) return null;

            switch (t.value) {
                case "sqrt": return arg >= 0 ? Math.sqrt(arg) : null;
                case "sin": return Math.sin(arg);
                case "cos": return Math.cos(arg);
                case "tan": return Math.tan(arg);
                case "abs": return Math.abs(arg);
                case "round": return Math.round(arg);
                case "floor": return Math.floor(arg);
                case "ceil": return Math.ceil(arg);
                case "log": return arg > 0 ? Math.log10(arg) : null;
                case "ln": return arg > 0 ? Math.log(arg) : null;
                case "exp": return Math.exp(arg);
                default: return null;
            }
        }

        if (t.type === "OP" && t.value === "(") {
            consume();
            const val = parseExpr();
            if (val === null || !consume(")")) return null;
            return val;
        }

        return null;
    }

    const res = parseExpr();
    if (res === null || pos < tokens.length) return null;
    return res;
}

function tryMathEvaluation(query) {
    let clean = query.trim();
    if (clean.indexOf("=") === 0) clean = clean.substring(1).trim();
    if (clean.length < 2) return null;

    // Must contain at least one math operator, constant, or known math function
    const isConstant = /^(pi|e)$/i.test(clean);
    const hasOp = isConstant || /[\+\-\*\/\^\%]|sqrt|sin|cos|tan|abs|log|ln|exp/i.test(clean);
    if (!hasOp) return null;

    // Handle percentage expressions like "20% of 150"
    clean = clean.replace(/([0-9]+(?:\.[0-9]+)?)\s*%\s+of\s+/i, "($1 / 100) * ");

    const tokens = tokenizeMath(clean.toLowerCase());
    if (!tokens || (tokens.length < 2 && !isConstant)) return null;

    const res = parseTokens(tokens);
    if (res === null || isNaN(res) || !isFinite(res)) return null;

    const formatted = formatNumber(res);
    if (formatted === null) return null;

    return {
        valid: true,
        type: "math",
        expression: clean + " = " + formatted,
        result: String(res),
        formattedResult: formatted,
        value: formatted
    };
}

// ── Main Entry ──────────────────────────────────────────────────────────────
function evaluate(query) {
    if (!query || typeof query !== "string") return { valid: false };
    const q = query.trim();
    if (q.length < 2) return { valid: false };

    // 1. Try unit/currency conversion
    const unitRes = tryUnitConversion(q);
    if (unitRes) return unitRes;

    // 2. Try math evaluation
    const mathRes = tryMathEvaluation(q);
    if (mathRes) return mathRes;

    return { valid: false };
}
