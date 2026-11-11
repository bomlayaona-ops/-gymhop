/* Region -> Province -> City/Municipality dropdowns (Philippines). Used by the .addr-picker block in macros.html */
(function () {
  document.querySelectorAll('.addr-picker').forEach(function (box) {
    fetch(box.dataset.src).then(function (r) { return r.json(); }).then(function (data) {
      const reg = box.querySelector('.addr-region'), prov = box.querySelector('.addr-province'),
            city = box.querySelector('.addr-city'), other = box.querySelector('.addr-other'),
            otherInput = other.querySelector('input');
      const init = { region: box.dataset.region, province: box.dataset.province, city: box.dataset.city };

      function fill(sel, items, placeholder) {
        sel.innerHTML = '';
        sel.add(new Option(placeholder, ''));
        items.forEach(function (i) { sel.add(new Option(i, i)); });
        sel.disabled = items.length === 0;
      }
      function showOther() {
        const on = city.value === '__other__';
        other.hidden = !on; otherInput.required = on;
        if (!on) otherInput.value = '';
      }
      function onCity() { showOther(); }
      function onProvince() {
        const places = (data[reg.value] || {})[prov.value] || [];
        fill(city, places, 'Choose city / municipality');
        if (prov.value) city.add(new Option('Other (type it below)', '__other__'));
        city.disabled = !prov.value;
        if (init.city) {
          if (places.indexOf(init.city) >= 0) city.value = init.city;
          else { city.value = '__other__'; otherInput.value = init.city; }
          init.city = '';
        }
        showOther();
      }
      function onRegion() {
        const provs = Object.keys(data[reg.value] || {});
        fill(prov, provs, 'Choose province');
        if (init.province && provs.indexOf(init.province) >= 0) { prov.value = init.province; init.province = ''; }
        else if (provs.length === 1) prov.value = provs[0];
        onProvince();
      }

      if (!init.region && init.province) {          // only a province was saved: find its region
        Object.keys(data).forEach(function (r) { if (data[r][init.province]) init.region = r; });
      }
      fill(reg, Object.keys(data), 'Choose region');
      if (init.region) reg.value = init.region;
      onRegion();
      reg.addEventListener('change', function () { init.city = ''; init.province = ''; onRegion(); });
      prov.addEventListener('change', function () { init.city = ''; onProvince(); });
      city.addEventListener('change', onCity);
    }).catch(function () {
      box.insertAdjacentHTML('beforeend', '<p class="muted-sm">The address list could not load. Refresh the page.</p>');
    });
  });
})();
