
def test():
    
    move_xyz(152, 128, 225)
    move_xyz(152, 128, 219)
    time.sleep(2)
    send_cmd(f"M104 S100")
    time.sleep(2)
    send_cmd(f"M104 S0")
    move_xyz(152, 128, 225)
    
    move_xyz(159, 128, 225)
    move_xyz(159, 128, 219)
    time.sleep(2)
    send_cmd(f"M104 S100")
    time.sleep(2)
    send_cmd(f"M104 S0")
    move_xyz(159, 128, 225)
    
    move_xyz(166, 128, 225)
    move_xyz(166, 128, 219)
    time.sleep(2)
    send_cmd(f"M104 S100")
    time.sleep(2)
    send_cmd(f"M104 S0")
    move_xyz(166, 128, 225)
    
    
    move_xyz(173, 128, 225)
    move_xyz(173, 128, 219)
    time.sleep(2)
    send_cmd(f"M104 S100")
    time.sleep(2)
    send_cmd(f"M104 S0")
    move_xyz(173, 128, 225)
    
    move_xyz(180, 128, 225)
    move_xyz(180, 128, 219)
    time.sleep(2)
    send_cmd(f"M104 S100")
    time.sleep(2)
    send_cmd(f"M104 S0")
    move_xyz(180, 128, 225)
