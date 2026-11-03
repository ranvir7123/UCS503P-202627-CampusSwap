const theme = require("./theme.cjs");

module.exports = {
  ...theme,
  content: ["./public/dashboard.html", "./public/js/dashboard.js", "./public/js/ring.js", "./public/js/ui.js", "./public/js/nav.js", "./src/tailwind.css"],
};
