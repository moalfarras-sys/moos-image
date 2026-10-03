"""Lumen — the MoOS lighting engine (every light in the house and in the computer as one system).

engine.py      lights, rooms, groups, words → lights, control with read-back, living scenes
scenes.py      the scene library        colors.py   colour names and conversions
pc.py          the computer's own lights (fusion2.py: the Gigabyte controller)
hue.py         the Hue bridge directly (dtls.py: the Entertainment stream's transport)
capture.py     the screen, through the ScreenCast portal   sync.py   reading colour from it
syncsession.py Screen Sync: lights follow the screen
service.py     the private socket        client.py   how Mira and Settings reach it
"""
