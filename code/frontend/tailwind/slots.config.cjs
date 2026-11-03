const theme = require("./theme.cjs");

module.exports = {
  ...theme,
  content: ["./public/slots.html", "./public/js/slots.js", "./public/js/ui.js", "./public/js/nav.js", "./src/tailwind.css"],
};
