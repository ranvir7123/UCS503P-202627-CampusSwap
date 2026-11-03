const theme = require("./theme.cjs");

module.exports = {
  ...theme,
  content: ["./public/index.html", "./public/js/login.js", "./public/js/ui.js", "./public/js/api.js", "./public/js/nav.js", "./src/tailwind.css"],
};
