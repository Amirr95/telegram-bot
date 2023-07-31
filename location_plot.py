import os
import database
import folium

db = database.Database()

locations = []
users = db.user_collection.distinct("_id")
iran_map = folium.Map(location=[32.4279, 53.6880], zoom_start=6)
for user in users:
    farms = db.get_farms(user)
    username = db.get_user_attribute(user, 'username')
    if not username: username = user
    if len(farms) == 1:
        if farms['باغ 1']['location']['longitude'] is not None:
            locations.append({'longitude': farms['باغ 1']['location']['longitude'],
                                'latitude': farms['باغ 1']['location']['latitude']})
            folium.Marker(location=[farms['باغ 1']['location']['latitude'], 
                                    farms['باغ 1']['location']['longitude']], 
                                    popup=username).add_to(iran_map)   
    else:
        farm_names = list(farms.keys())
        for i, farm in enumerate(farm_names):
            if farms[farm]['location']['longitude'] is not None:
                folium.Marker(location=[farms[farm]['location']['latitude'], 
                                        farms[farm]['location']['longitude']], 
                                        popup=f"{username}-1").add_to(iran_map)

iran_map.save("iran_map2.html")  # Save the map as an HTML file