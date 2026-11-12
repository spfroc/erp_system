/**
 * 统一中文日期选择器（flatpickr）：格式固定 yyyy-mm-dd。
 * 用法：
 *   ycDatePicker.bind(input)
 *   ycDatePicker.bindAll(root, "input.date-input")
 */
(function (global) {
  function locale() {
    if (global.flatpickr && global.flatpickr.l10ns && global.flatpickr.l10ns.zh) {
      return global.flatpickr.l10ns.zh;
    }
    return "zh";
  }

  function bind(input, options) {
    if (!input || !global.flatpickr) return null;
    if (input._flatpickr) {
      try {
        input._flatpickr.destroy();
      } catch (error) {
        /* ignore */
      }
    }
    var opts = Object.assign(
      {
        locale: locale(),
        dateFormat: "Y-m-d",
        altInput: false,
        allowInput: true,
        disableMobile: true,
        monthSelectorType: "static",
      },
      options || {}
    );
    return global.flatpickr(input, opts);
  }

  function bindAll(root, selector, options) {
    var scope = root || document;
    var nodes = scope.querySelectorAll(selector || "input.date-input, input[data-datepicker]");
    var instances = [];
    Array.prototype.forEach.call(nodes, function (input) {
      instances.push(bind(input, options));
    });
    return instances;
  }

  global.ycDatePicker = {
    bind: bind,
    bindAll: bindAll,
  };
})(window);
