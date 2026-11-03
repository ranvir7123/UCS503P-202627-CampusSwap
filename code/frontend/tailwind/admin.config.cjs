const theme = require("./theme.cjs");

module.exports = {
  ...theme,
  content: ["./public/admin.html", "./public/js/admin.js", "./public/js/ui.js", "./public/js/nav.js", "./src/tailwind.css"],
};
