const theme = require("./theme.cjs");

module.exports = {
  ...theme,
  content: ["./public/rooms.html", "./public/js/rooms.js", "./public/js/ui.js", "./public/js/api.js", "./public/js/nav.js", "./src/tailwind.css"],
};
