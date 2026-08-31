/* =========================================================
   GLOWISD — front-end scripts (Vue 3 global build)   V0.3.6
   组件：语言切换 · 移动导航 · 询价表单（fetch POST）
   ========================================================= */
(function () {
  'use strict';
  if (typeof Vue === 'undefined') return;
  var createApp = Vue.createApp;

  /* ---- 1. 语言切换 Language switcher（桌面 + 移动多挂载点） ---- */
  var switcherEls = document.querySelectorAll('[data-lang-switcher]');
  if (switcherEls.length) {
    var switcherDef = {
      data: function () {
        return {
          lang: document.documentElement.getAttribute('lang') === 'en' ? 'en' : 'zh'
        };
      },
      methods: {
        setLang: function (l) {
          if (l === this.lang) return;
          document.cookie = 'lang=' + l + '; path=/; max-age=31536000; SameSite=Lax';
          window.location.reload();
        }
      },
      template:
        '<div class="lang-switch" role="group" aria-label="Language switch">' +
        '<button type="button" :class="{\'is-active\': lang === \'zh\'}" @click="setLang(\'zh\')">中</button>' +
        '<button type="button" :class="{\'is-active\': lang === \'en\'}" @click="setLang(\'en\')">EN</button>' +
        '</div>'
    };
    switcherEls.forEach(function (el) {
      createApp(switcherDef).mount(el);
    });
  }

  /* ---- 2. 移动导航 Mobile nav toggle ---- */
  var navToggle = document.getElementById('nav-toggle');
  var mobileNav = document.getElementById('mobile-nav');
  if (navToggle && mobileNav) {
    navToggle.addEventListener('click', function () {
      var open = mobileNav.classList.toggle('is-open');
      navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  /* ---- 3. 询价表单 Inquiry / contact form ---- */
  var contactEl = document.getElementById('contact-app');
  if (contactEl) {
    var qs = new URLSearchParams(window.location.search);
    var prefProduct = qs.get('product') || '';
    var prefCategory = qs.get('category') || '';

    createApp({
      data: function () {
        var en = contactEl.getAttribute('data-lang') === 'en';
        return {
          lang: en ? 'en' : 'zh',
          form: {
            name: '',
            company: '',
            email: '',
            phone: '',
            country: '',
            category: prefCategory,
            message: prefProduct ? '[Product: ' + prefProduct + ']\n' : '',
            product: prefProduct, /* 隐藏字段：产品详情页跳转带来的 sku，随表单提交用于关联 inquired_product */
            website: '' /* honeypot */
          },
          submitting: false,
          ok: false,
          error: '',
          rateLimited: false,
          csrf: '',
          okText: en ? 'Submitted! We will contact you soon.' : '提交成功，我们会尽快与您联系！',
          submitText: en ? 'Send Inquiry' : '提交询价',
          sendingText: en ? 'Sending…' : '提交中…'
        };
      },
      created: function () {
        var el = contactEl.querySelector('input[name="csrfmiddlewaretoken"]');
        if (el) { this.csrf = el.value; return; }
        var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        if (m) { this.csrf = decodeURIComponent(m[1]); }
      },
      methods: {
        i18n: function (zh, en) { return this.lang === 'en' ? en : zh; },
        submit: function () {
          var self = this;
          var f = this.form;
          var emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

          this.error = '';
          this.ok = false;
          this.rateLimited = false;

          if (!f.name.trim()) { this.error = this.i18n('请填写姓名', 'Please enter your name.'); return; }
          if (!f.email.trim()) { this.error = this.i18n('请填写邮箱', 'Please enter your email.'); return; }
          if (!emailRe.test(f.email.trim())) { this.error = this.i18n('邮箱格式不正确', 'Please enter a valid email address.'); return; }
          if (!f.message.trim()) { this.error = this.i18n('请填写留言内容', 'Please enter your message.'); return; }

          var fd = new FormData();
          Object.keys(f).forEach(function (k) { fd.append(k, f[k]); });

          this.submitting = true;
          fetch('/contact/', {
            method: 'POST',
            headers: {
              'X-CSRFToken': this.csrf,
              'X-Requested-With': 'XMLHttpRequest'
            },
            body: fd,
            credentials: 'same-origin'
          })
            .then(function (res) {
              return res.json().catch(function () { return {}; })
                .then(function (data) { return { res: res, data: data }; });
            })
            .then(function (r) {
              if (r.res.ok && r.data && r.data.ok) {
                self.ok = true;
                self.form.name = ''; self.form.company = ''; self.form.email = '';
                self.form.phone = ''; self.form.country = ''; self.form.category = '';
                self.form.message = ''; self.form.product = ''; self.form.website = '';
              } else {
                self.error = (r.data && r.data.error) ||
                  self.i18n('提交失败，请稍后再试', 'Submission failed. Please try again later.');
                if (r.data && r.data.rate_limited) { self.rateLimited = true; }
              }
            })
            .catch(function () {
              self.error = self.i18n('网络错误，请稍后再试', 'Network error. Please try again later.');
            })
            .then(function () { self.submitting = false; });
        }
      }
    }).mount(contactEl);
  }
})();
