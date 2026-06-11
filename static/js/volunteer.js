const socket = io();

socket.on('new_request', function(data){

alert(
"🚨 New Emergency!\n\n" +
data.category +
"\nPriority: " +
data.priority
);

});

var map = L.map('map');

map.setView(
[volunteerLat, volunteerLon],
14
);

L.tileLayer(
'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
{
maxZoom:19
}
).addTo(map);

L.marker(
[volunteerLat, volunteerLon]
)
.addTo(map)
.bindPopup("📍 You are here");

requestData.forEach(req=>{

L.circleMarker(
[req.lat, req.lon],
{
radius:10,
color:"red",
fillColor:"red",
fillOpacity:0.8
}
)
.addTo(map)
.bindPopup(
"<b>"+req.category+"</b><br>" +
req.address +
"<br>" +
req.distance +
" KM Away"
);

});

window.addEventListener("load",function(){
map.invalidateSize();
});

setInterval(function(){
location.reload();
},30000);