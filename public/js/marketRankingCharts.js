// marketRankingCharts.js — Apache ECharts interop for Market Ranking Charts
// Manages chart lifecycle, IntersectionObserver, and theme token extraction

(function () {
  'use strict';

  var chartInstances = [];
  var observer = null;
  var resizeObserver = null;
  var onBarClickCallback = null;

  // Read CSS variable value from :root
  function getCSSVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  // Extract theme tokens from CSS variables
  function getThemeTokens() {
    return {
      primary: getCSSVar('--primary') || '#1e3a5f',
      primaryHover: getCSSVar('--primary-hover') || '#152a45',
      success: getCSSVar('--success') || '#10b981',
      warning: getCSSVar('--warning') || '#f59e0b',
      textPrimary: getCSSVar('--text-primary') || '#1e293b',
      textSecondary: getCSSVar('--text-secondary') || '#475569',
      textMuted: getCSSVar('--text-muted') || '#64748b',
      bgCard: getCSSVar('--bg-card') || '#ffffff',
      bgSubtle: getCSSVar('--bg-subtle') || '#f1f5f9',
    };
  }

  // Format price for axis labels
  function formatPrice(value) {
    if (value >= 1000000) return '$' + (value / 1000000).toFixed(1) + 'M';
    if (value >= 1000) return '$' + Math.round(value / 1000) + 'K';
    return '$' + value;
  }

  // Build ECharts option for a horizontal bar chart (ranking)
  function buildHorizontalBarOption(title, subtitle, dataPoints, tokens, seriesColor) {
    var labels = dataPoints.map(function (d) { return d.label; });
    var values = dataPoints.map(function (d) { return d.y; });
    var isPrice = subtitle.indexOf('Mediana') >= 0;

    return {
      animation: true,
      animationDuration: 600,
      animationEasing: 'cubicOut',
      backgroundColor: 'transparent',
      title: [
        {
          text: title,
          left: 'center',
          top: 0,
          textStyle: {
            fontFamily: 'Inter, sans-serif',
            fontWeight: 'bold',
            fontSize: 15,
            color: tokens.textPrimary,
          },
        },
        {
          text: subtitle,
          left: 'center',
          top: 22,
          textStyle: {
            fontFamily: 'Inter, sans-serif',
            fontSize: 12,
            fontWeight: 'normal',
            color: tokens.textMuted,
          },
        }
      ],
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        renderMode: 'html',
        appendToBody: true,
        confine: false,
        backgroundColor: tokens.bgCard,
        borderColor: tokens.bgSubtle,
        borderWidth: 1,
        textStyle: {
          fontFamily: 'Inter, sans-serif',
          fontSize: 13,
          color: tokens.textPrimary,
        },
        position: function (point, params, dom, rect, size) {
          var x = point[0] + 10;
          var y = point[1] - size.contentSize[1] / 2;
          var vw = window.innerWidth;
          var vh = window.innerHeight;
          var margin = 10;
          if (x + size.contentSize[0] > vw - margin) x = point[0] - size.contentSize[0] - 10;
          if (x < margin) x = margin;
          if (y + size.contentSize[1] > vh - margin) y = vh - margin - size.contentSize[1];
          if (y < margin) y = margin;
          return [x, y];
        },
        formatter: function (params) {
          var p = params[0];
          var dp = dataPoints[p.dataIndex];
          var metricLabel = isPrice ? 'Precio típico (mediana)' : 'Activos hoy';
          var valueStr = dp.indexLabel || p.value.toLocaleString();
          return '<strong>' + p.name + '</strong><br/>' +
            metricLabel + ': <strong>' + valueStr + '</strong>';
        },
      },
      grid: {
        left: 10,
        right: 80,
        top: 52,
        bottom: 5,
        containLabel: true,
      },
      xAxis: {
        type: 'value',
        show: false,
      },
      yAxis: {
        type: 'category',
        data: labels,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: {
          fontFamily: 'Inter, sans-serif',
          fontSize: 12,
          color: tokens.textSecondary,
          width: 90,
          overflow: 'truncate',
        },
      },
      series: [{
        type: 'bar',
        data: values,
        barMaxWidth: 28,
        itemStyle: {
          color: seriesColor,
          borderRadius: [0, 4, 4, 0],
        },
        label: {
          show: true,
          position: 'right',
          fontFamily: 'Inter, sans-serif',
          fontSize: 12,
          fontWeight: 'bold',
          color: tokens.textPrimary,
          formatter: function (p) {
            return dataPoints[p.dataIndex] ? dataPoints[p.dataIndex].indexLabel : '';
          },
        },
        emphasis: {
          itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.15)' },
        },
      }],
    };
  }

  // Build ECharts option for a vertical column chart
  function buildColumnOption(title, subtitle, dataPoints, tokens, seriesColor) {
    var labels = dataPoints.map(function (d) { return d.label; });
    var values = dataPoints.map(function (d) { return d.y; });

    return {
      animation: true,
      animationDuration: 600,
      animationEasing: 'cubicOut',
      backgroundColor: 'transparent',
      title: [
        {
          text: title,
          left: 'center',
          top: 0,
          textStyle: {
            fontFamily: 'Inter, sans-serif',
            fontWeight: 'bold',
            fontSize: 15,
            color: tokens.textPrimary,
          },
        },
        {
          text: subtitle,
          left: 'center',
          top: 22,
          textStyle: {
            fontFamily: 'Inter, sans-serif',
            fontSize: 12,
            fontWeight: 'normal',
            color: tokens.textMuted,
          },
        }
      ],
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        renderMode: 'html',
        appendToBody: true,
        confine: false,
        backgroundColor: tokens.bgCard,
        borderColor: tokens.bgSubtle,
        borderWidth: 1,
        textStyle: {
          fontFamily: 'Inter, sans-serif',
          fontSize: 13,
          color: tokens.textPrimary,
        },
        position: function (point, params, dom, rect, size) {
          var x = point[0] + 10;
          var y = point[1] - size.contentSize[1] / 2;
          var vw = window.innerWidth;
          var vh = window.innerHeight;
          var margin = 10;
          if (x + size.contentSize[0] > vw - margin) x = point[0] - size.contentSize[0] - 10;
          if (x < margin) x = margin;
          if (y + size.contentSize[1] > vh - margin) y = vh - margin - size.contentSize[1];
          if (y < margin) y = margin;
          return [x, y];
        },
        formatter: function (params) {
          var p = params[0];
          var dp = dataPoints[p.dataIndex];
          var valueStr = dp.indexLabel || p.value.toLocaleString();
          return '<strong>' + p.name + '</strong><br/>' +
            'Activos hoy: <strong>' + valueStr + '</strong>';
        },
      },
      grid: {
        left: 10,
        right: 10,
        top: 52,
        bottom: 45,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: labels,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: {
          interval: 0,
          fontFamily: 'Inter, sans-serif',
          fontSize: 12,
          color: tokens.textSecondary,
          width: 80,
          overflow: 'truncate',
          ellipsis: '…',
        },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: {
          show: true,
          lineStyle: { color: tokens.bgSubtle, type: 'dashed' },
        },
        axisLabel: {
          fontFamily: 'Inter, sans-serif',
          fontSize: 11,
          color: tokens.textMuted,
          formatter: function (v) { return v.toLocaleString(); },
        },
      },
      series: [{
        type: 'bar',
        data: values,
        barMaxWidth: 48,
        itemStyle: {
          color: seriesColor,
          borderRadius: [4, 4, 0, 0],
        },
        label: {
          show: true,
          position: 'top',
          fontFamily: 'Inter, sans-serif',
          fontSize: 12,
          fontWeight: 'bold',
          color: tokens.textPrimary,
          formatter: function (p) {
            return dataPoints[p.dataIndex] ? dataPoints[p.dataIndex].indexLabel : '';
          },
        },
        emphasis: {
          itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.15)' },
        },
      }],
    };
  }

  // Build ECharts option for a line/area chart (monthly evolution)
  function buildLineAreaOption(title, subtitle, months, values, tokens, lineColor) {
    return {
      animation: true,
      animationDuration: 600,
      animationEasing: 'cubicOut',
      backgroundColor: 'transparent',
      title: [
        {
          text: title,
          left: 'center',
          top: 0,
          textStyle: {
            fontFamily: 'Inter, sans-serif',
            fontWeight: 'bold',
            fontSize: 15,
            color: tokens.textPrimary,
          },
        },
        {
          text: subtitle,
          left: 'center',
          top: 22,
          textStyle: {
            fontFamily: 'Inter, sans-serif',
            fontSize: 12,
            fontWeight: 'normal',
            color: tokens.textMuted,
          },
        }
      ],
      tooltip: {
        trigger: 'axis',
        renderMode: 'html',
        appendToBody: true,
        confine: false,
        backgroundColor: tokens.bgCard,
        borderColor: tokens.bgSubtle,
        borderWidth: 1,
        textStyle: {
          fontFamily: 'Inter, sans-serif',
          fontSize: 13,
          color: tokens.textPrimary,
        },
        formatter: function (params) {
          var p = params[0];
          return '<strong>' + p.name + ' 2025</strong><br/>' +
            'Precio medio: <strong>' + formatPrice(p.value) + '</strong>';
        },
      },
      grid: {
        left: 10,
        right: 20,
        top: 52,
        bottom: 30,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: months,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          fontFamily: 'Inter, sans-serif',
          fontSize: 11,
          color: tokens.textMuted,
        },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: {
          show: true,
          lineStyle: { color: tokens.bgSubtle, type: 'dashed' },
        },
        axisLabel: {
          fontFamily: 'Inter, sans-serif',
          fontSize: 11,
          color: tokens.textMuted,
          formatter: function (v) { return formatPrice(v); },
        },
      },
      series: [{
        type: 'line',
        data: values,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          color: lineColor,
          width: 3,
        },
        itemStyle: {
          color: lineColor,
          borderColor: '#fff',
          borderWidth: 2,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: lineColor + '33' },
              { offset: 1, color: lineColor + '05' },
            ],
          },
        },
        emphasis: {
          itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.15)' },
        },
      }],
    };
  }

  // Attach click handler to an ECharts instance
  function attachClickHandler(chart, dataPoints) {
    chart.on('click', function (params) {
      if (onBarClickCallback && dataPoints[params.dataIndex]) {
        onBarClickCallback(dataPoints[params.dataIndex].id);
      }
    });
    // Make bars show pointer cursor
    chart.getZr().on('mousemove', function (e) {
      var el = chart.containPixel('grid', [e.offsetX, e.offsetY]);
      chart.getZr().setCursorStyle(el ? 'pointer' : 'default');
    });
  }

  // Setup ResizeObserver for responsive charts
  function setupResizeObserver(containerIds) {
    if (resizeObserver) resizeObserver.disconnect();

    resizeObserver = new ResizeObserver(function () {
      chartInstances.forEach(function (c) {
        if (c) c.resize();
      });
    });

    containerIds.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) resizeObserver.observe(el);
    });
  }

  window.MarketRankingCharts = {
    initCharts: function (config) {
      if (typeof echarts === 'undefined') {
        console.warn('ECharts not loaded yet');
        return false;
      }

      var tokens = getThemeTokens();
      onBarClickCallback = config.onBarClick || null;

      // Destroy previous if any
      this.destroyCharts();

      var expData = config.expensiveData || [];
      var chpData = config.cheapData || [];
      var actData = config.activeData || [];

      // Chart A: Zonas Más Caras (horizontal bar)
      var elA = document.getElementById(config.containerIds[0]);
      var chartA = echarts.getInstanceByDom(elA) || echarts.init(elA);
      chartA.setOption(buildHorizontalBarOption('ZONAS MÁS CARAS', '(Precio Típico Mediana)', expData, tokens, tokens.success));
      attachClickHandler(chartA, expData);

      // Chart B: Zonas Más Económicas (horizontal bar)
      var elB = document.getElementById(config.containerIds[1]);
      var chartB = echarts.getInstanceByDom(elB) || echarts.init(elB);
      chartB.setOption(buildHorizontalBarOption('ZONAS MÁS ECONÓMICAS', '(Precio Típico Mediana)', chpData, tokens, tokens.primary));
      attachClickHandler(chartB, chpData);

      // Chart C: Zonas Más Activas (column)
      var elC = document.getElementById(config.containerIds[2]);
      var chartC = echarts.getInstanceByDom(elC) || echarts.init(elC);
      chartC.setOption(buildColumnOption('ZONAS MÁS ACTIVAS', '(Activos Hoy)', actData, tokens, tokens.warning));
      attachClickHandler(chartC, actData);

      chartInstances = [chartA, chartB, chartC];

      // Chart D: Precio Medio por Departamento (horizontal bar — all depts)
      var deptPriceData = config.deptPriceData || [];
      if (deptPriceData.length > 0) {
        var elD = document.getElementById('chart-dept-price');
        if (elD) {
          var chartD = echarts.getInstanceByDom(elD) || echarts.init(elD);
          chartD.setOption(buildHorizontalBarOption('PRECIO MEDIO POR DEPARTAMENTO', '(Precio Típico Mediana)', deptPriceData, tokens, tokens.primary));
          attachClickHandler(chartD, deptPriceData);
          chartInstances.push(chartD);
        }
      }

      // Chart E: Evolución Mensual (line/area)
      var monthlyData = config.monthlyData || { months: [], values: [] };
      if (monthlyData.months.length > 0) {
        var elE = document.getElementById('chart-monthly');
        if (elE) {
          var chartE = echarts.getInstanceByDom(elE) || echarts.init(elE);
          chartE.setOption(buildLineAreaOption('EVOLUCIÓN MENSUAL (2025)', '(Precio Medio Nacional)', monthlyData.months, monthlyData.values, tokens, tokens.success));
          chartInstances.push(chartE);
        }
      }

      // Responsive resize
      var allIds = (config.containerIds || []).concat(['chart-dept-price', 'chart-monthly']);
      setupResizeObserver(allIds);

      return true;
    },

    // Update data without destroying charts — smooth transition
    updateChartData: function (chartIndex, dataPoints) {
      if (!chartInstances[chartIndex]) return;
      var chart = chartInstances[chartIndex];
      var values = dataPoints.map(function (d) { return d.y; });
      var labels = dataPoints.map(function (d) { return d.label; });

      chart.setOption({
        yAxis: { data: labels },
        series: [{
          data: values,
          label: {
            formatter: function (p) {
              return dataPoints[p.dataIndex] ? dataPoints[p.dataIndex].indexLabel : '';
            },
          },
        }],
      });
    },

    updateAllCharts: function (expensiveData, cheapData, activeData, deptPriceData, monthlyData) {
      if (chartInstances.length < 3) return;

      var tokens = getThemeTokens();

      // Chart A — horizontal bar
      chartInstances[0].setOption(buildHorizontalBarOption('ZONAS MÁS CARAS', '(Precio Típico Mediana)', expensiveData, tokens, tokens.success));
      attachClickHandler(chartInstances[0], expensiveData);

      // Chart B — horizontal bar
      chartInstances[1].setOption(buildHorizontalBarOption('ZONAS MÁS ECONÓMICAS', '(Precio Típico Mediana)', cheapData, tokens, tokens.primary));
      attachClickHandler(chartInstances[1], cheapData);

      // Chart C — column
      chartInstances[2].setOption(buildColumnOption('ZONAS MÁS ACTIVAS', '(Activos Hoy)', activeData, tokens, tokens.warning));
      attachClickHandler(chartInstances[2], activeData);

      // Chart D — dept price (if initialized)
      if (chartInstances[3] && deptPriceData && deptPriceData.length > 0) {
        chartInstances[3].setOption(buildHorizontalBarOption('PRECIO MEDIO POR DEPARTAMENTO', '(Precio Típico Mediana)', deptPriceData, tokens, tokens.primary));
        attachClickHandler(chartInstances[3], deptPriceData);
      }

      // Chart E — monthly evolution (if initialized)
      if (chartInstances[4] && monthlyData && monthlyData.months.length > 0) {
        chartInstances[4].setOption(buildLineAreaOption('EVOLUCIÓN MENSUAL (2025)', '(Precio Medio Nacional)', monthlyData.months, monthlyData.values, tokens, tokens.success));
      }
    },

    // Destroy all chart instances
    destroyCharts: function () {
      chartInstances.forEach(function (c) {
        if (c && c.dispose) c.dispose();
      });
      chartInstances = [];
      if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
      }
    },

    // IntersectionObserver for lazy load
    observeSection: function (elementId, onVisible, onHidden) {
      var el = document.getElementById(elementId);
      if (!el) return;

      if (observer) observer.disconnect();

      observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            if (onVisible) onVisible();
          } else {
            if (onHidden) onHidden();
          }
        });
      }, { threshold: 0.3 });

      observer.observe(el);
    },

    // Disconnect observer
    disconnectObserver: function () {
      if (observer) {
        observer.disconnect();
        observer = null;
      }
    },

    // Check if ECharts is loaded
    isReady: function () {
      return typeof echarts !== 'undefined';
    }
  };
})();
