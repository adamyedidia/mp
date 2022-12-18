from math import sqrt

FLASHLIGHT_COLOR = (255, 255, 0)

def get_unit_vector_from_player_to_mouse(player_x: int, player_y: int, mouse_x: int, mouse_y: int):
    vector_from_player_to_mouse = (mouse_x - player_x, mouse_y - player_y)
    vector_from_player_to_mouse_mag = sqrt(vector_from_player_to_mouse[0]**2 + vector_from_player_to_mouse[1]**2)
    unit_vector_from_player_to_mouse = (vector_from_player_to_mouse[0] / vector_from_player_to_mouse_mag,
                                        vector_from_player_to_mouse[1] / vector_from_player_to_mouse_mag)
    return unit_vector_from_player_to_mouse


def get_flashlight_triangle(player_x: int, player_y: int, mouse_x: int, mouse_y: int):
    flashlight_range = 200
    flashlight_width = 50
    
    unit_vector_from_player_to_mouse = get_unit_vector_from_player_to_mouse(player_x, player_y, mouse_x, mouse_y)
    perp_unit_vector = (unit_vector_from_player_to_mouse[1], -unit_vector_from_player_to_mouse[0])

    point_1 = (player_x, player_y)
    point_2 = [point_1[i] + flashlight_range * unit_vector_from_player_to_mouse[i] + flashlight_width * perp_unit_vector[i] for i in range(2)]
    point_3 = [point_1[i] + flashlight_range * unit_vector_from_player_to_mouse[i] - flashlight_width * perp_unit_vector[i]
                               for i in range(2)]

    return (point_1, point_2, point_3)


def point_in_triangle(point, triangle):
    """Returns True if the point is inside the triangle
    and returns False if it falls outside.
    - The argument *point* is a tuple with two elements
    containing the X,Y coordinates respectively.
    - The argument *triangle* is a tuple with three elements each
    element consisting of a tuple of X,Y coordinates.

    It works like this:
    Walk clockwise or counterclockwise around the triangle
    and project the point onto the segment we are crossing
    by using the dot product.
    Finally, check that the vector created is on the same side
    for each of the triangle's segments.
    """
    # Unpack arguments
    x, y = point
    ax, ay = triangle[0]
    bx, by = triangle[1]
    cx, cy = triangle[2]
    # Segment A to B
    side_1 = (x - bx) * (ay - by) - (ax - bx) * (y - by)
    # Segment B to C
    side_2 = (x - cx) * (by - cy) - (bx - cx) * (y - cy)
    # Segment C to A
    side_3 = (x - ax) * (cy - ay) - (cx - ax) * (y - ay)
    # All the signs must be positive or all negative
    return (side_1 < 0.0) == (side_2 < 0.0) == (side_3 < 0.0)
