/* =========================================================
   GLOWISD — front-end scripts (Vue 3 global build)   V0.4.1
   组件：语言切换 · 移动导航 · 询价表单（fetch POST）
   ========================================================= */
(function () {
  'use strict';
  if (typeof Vue === 'undefined') return;
  var createApp = Vue.createApp;

  /* ---- 1. 语言切换 Language switcher（中 / EN / عربي 三态，桌面 + 移动多挂载点） ---- */
  var switcherEls = document.querySelectorAll('[data-lang-switcher]');
  if (switcherEls.length) {
    var currentLang = document.documentElement.getAttribute('lang') || 'zh';
    var switcherDef = {
      data: function () {
        return { lang: currentLang };
      },
      methods: {
        setLang: function (l) {
          if (l === this.lang) return;
          document.cookie = 'lang=' + l + '; path=/; max-age=31536000; SameSite=Lax';
          document.cookie = 'lang_chosen=1; path=/; max-age=31536000; SameSite=Lax';
          window.location.reload();
        }
      },
      template:
        '<div class="lang-switch" role="group" aria-label="Language switch">' +
        '<button type="button" :class="{\'is-active\': lang === \'zh\'}" @click="setLang(\'zh\')">中</button>' +
        '<button type="button" :class="{\'is-active\': lang === \'en\'}" @click="setLang(\'en\')">EN</button>' +
        '<button type="button" :class="{\'is-active\': lang === \'ar\'}" @click="setLang(\'ar\')">عربي</button>' +
        '</div>'
    };
    switcherEls.forEach(function (el) {
      createApp(switcherDef).mount(el);
    });
  }

  /* ---- 1b. 首次进入语言选择弹窗（仅首次：cookie lang_chosen 不存在时由后端渲染） ---- */
  var langModal = document.getElementById('lang-modal');
  if (langModal) {
    var chooseLang = function (l) {
      if (l) {
        document.cookie = 'lang=' + l + '; path=/; max-age=31536000; SameSite=Lax';
      }
      document.cookie = 'lang_chosen=1; path=/; max-age=31536000; SameSite=Lax';
      langModal.classList.add('is-closing');
      setTimeout(function () { window.location.reload(); }, 160);
    };
    langModal.querySelectorAll('[data-pick-lang]').forEach(function (btn) {
      btn.addEventListener('click', function () { chooseLang(btn.getAttribute('data-pick-lang')); });
    });
    var closeBtn = langModal.querySelector('[data-close-modal]');
    if (closeBtn) closeBtn.addEventListener('click', function () { chooseLang(null); });
    langModal.addEventListener('click', function (e) {
      if (e.target === langModal) chooseLang(null);
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
        var cur = document.documentElement.getAttribute('lang') || contactEl.getAttribute('data-lang') || 'zh';
        var isAr = cur === 'ar';
        var isEn = cur === 'en';
        return {
          lang: cur,
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
          okText: isAr ? 'تم الإرسال بنجاح، سنتواصل معك قريباً.'
            : isEn ? 'Submitted! We will contact you soon.' : '提交成功，我们会尽快与您联系！',
          submitText: isAr ? 'إرسال طلب عرض السعر'
            : isEn ? 'Send Inquiry' : '提交询价',
          sendingText: isAr ? 'جارٍ الإرسال…'
            : isEn ? 'Sending…' : '提交中…'
        };
      },
      created: function () {
        var el = contactEl.querySelector('input[name="csrfmiddlewaretoken"]');
        if (el) { this.csrf = el.value; return; }
        var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        if (m) { this.csrf = decodeURIComponent(m[1]); }
      },
      methods: {
        i18n: function (zh, en, ar) {
          if (this.lang === 'ar') return ar || en;
          return this.lang === 'en' ? en : zh;
        },
        submit: function () {
          var self = this;
          var f = this.form;
          var emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

          this.error = '';
          this.ok = false;
          this.rateLimited = false;

          if (!f.name.trim()) { this.error = this.i18n('请填写姓名', 'Please enter your name.', 'يرجى إدخال اسمك.'); return; }
          if (!f.email.trim()) { this.error = this.i18n('请填写邮箱', 'Please enter your email.', 'يرجى إدخال بريدك الإلكتروني.'); return; }
          if (!emailRe.test(f.email.trim())) { this.error = this.i18n('邮箱格式不正确', 'Please enter a valid email address.', 'يرجى إدخال بريد إلكتروني صالح.'); return; }
          if (!f.message.trim()) { this.error = this.i18n('请填写留言内容', 'Please enter your message.', 'يرجى إدخال رسالتك.'); return; }

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
                  self.i18n('提交失败，请稍后再试', 'Submission failed. Please try again later.', 'فشل الإرسال، يرجى المحاولة لاحقاً.');
                if (r.data && r.data.rate_limited) { self.rateLimited = true; }
              }
            })
            .catch(function () {
              self.error = self.i18n('网络错误，请稍后再试', 'Network error. Please try again later.', 'خطأ في الشبكة، يرجى المحاولة لاحقاً.');
            })
            .then(function () { self.submitting = false; });
        }
      }
    }).mount(contactEl);
  }
})();

/* =========================================================
   V0.13.0 — 导航增强（独立 IIFE，不依赖 Vue）：
   · 下滑收起 / 上滑出现的吸顶导航
   · 「产品」二级菜单：hover intent + 键盘 + 触屏点击
   · 移动端产品分类折叠
   ========================================================= */
(function () {
  'use strict';
  var header = document.querySelector('.site-header');
  if (!header) return;
  var mobileNav = document.getElementById('mobile-nav');

  /* ---- 滚动方向检测 ---- */
  var lastY = window.scrollY || window.pageYOffset || 0;
  var ticking = false;
  var THRESHOLD = 6;

  function syncHeader() {
    ticking = false;
    var y = window.scrollY || window.pageYOffset || 0;
    header.classList.toggle('is-scrolled', y > 6);

    var menuOpen = !!(mobileNav && mobileNav.classList.contains('is-open'));
    var subOpen = !!header.querySelector('.nav-item--sub.is-open');

    if (y <= 90 || menuOpen || subOpen) {
      header.classList.remove('is-hidden');
    } else if (y > lastY + THRESHOLD) {
      header.classList.add('is-hidden');
    } else if (y < lastY - THRESHOLD) {
      header.classList.remove('is-hidden');
    }
    lastY = y;
  }

  function onScroll() {
    if (!ticking) {
      ticking = true;
      window.requestAnimationFrame(syncHeader);
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  syncHeader();

  /* ---- 产品二级菜单 ---- */
  var sub = document.querySelector('[data-nav-sub]');
  if (sub) {
    var trigger = sub.querySelector('.nav-link');
    var closeTimer = null;
    var canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

    function openSub() {
      clearTimeout(closeTimer);
      sub.classList.add('is-open');
      if (trigger) trigger.setAttribute('aria-expanded', 'true');
    }

    function closeSub(delay) {
      clearTimeout(closeTimer);
      closeTimer = setTimeout(function () {
        sub.classList.remove('is-open');
        if (trigger) trigger.setAttribute('aria-expanded', 'false');
      }, typeof delay === 'number' ? delay : 140);
    }

    if (canHover) {
      sub.addEventListener('mouseenter', openSub);
      sub.addEventListener('mouseleave', function () { closeSub(180); });
    }
    sub.addEventListener('focusin', openSub);
    sub.addEventListener('focusout', function (e) {
      if (!sub.contains(e.relatedTarget)) closeSub(0);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && sub.classList.contains('is-open')) {
        sub.classList.remove('is-open');
        if (trigger) {
          trigger.setAttribute('aria-expanded', 'false');
          trigger.focus();
        }
      }
    });

    /* 触屏：第一次点展开分类，再点进入产品列表 */
    if (!canHover && trigger) {
      trigger.addEventListener('click', function (e) {
        if (sub.classList.contains('is-open')) return;
        e.preventDefault();
        openSub();
      });
      document.addEventListener('click', function (e) {
        if (!sub.contains(e.target)) closeSub(0);
      });
    }

    sub.querySelectorAll('.nav-sub-item, .nav-sub-all').forEach(function (a) {
      a.addEventListener('click', function () { closeSub(0); });
    });
  }

  /* ---- 移动端分类折叠 ---- */
  var mobileSubToggle = document.querySelector('[data-mobile-sub]');
  var mobileSubBody = mobileSubToggle && mobileSubToggle.parentElement.querySelector('.mobile-sub-body');
  if (mobileSubToggle && mobileSubBody) {
    mobileSubToggle.addEventListener('click', function () {
      var open = mobileSubBody.classList.toggle('is-open');
      mobileSubToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
})();
