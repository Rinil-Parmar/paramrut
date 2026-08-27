$(document).ready(function() {
	$(".wordMeaning").fancybox({
		fitToView: false,
		width: "100%",
		height: "100%",
		autoSize: false,
		closeClick: false,
		openEffect: 'none',
		closeEffect: 'none',
		padding: 15
	});

	$('.inc_fontsize').click(function(event) {
		/* Act on the event */
		var fontSize = parseInt($("body").css("font-size"));
		fontSize = fontSize + 1 + "px";
		$("body").css({'font-size':fontSize});
	});
	$('.dec_fontsize').click(function(event) {
		/* Act on the event */
		var fontSize = parseInt($("body").css("font-size"));
		fontSize = fontSize - 1 + "px";
		$("body").css({'font-size':fontSize});
	});

});