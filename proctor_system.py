import cv2
import mediapipe as mp
import numpy as np
import time
import getpass
import google.generativeai as genai

# ==========================================
# USER INPUT SETUP
# ==========================================
print("--- AI Smart Classroom Security Setup ---")
USER_NAME = input("Enter your Name: ")
USER_API_KEY = getpass.getpass("Enter your Google Gemini API Key (Leave blank for Simulation Mode): ")

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================
# Eye Landmarks (Facial Mesh)
LEFT_EYE_INNER = 133
LEFT_EYE_OUTER = 33
LEFT_IRIS_CENTER = 468

RIGHT_EYE_INNER = 362
RIGHT_EYE_OUTER = 263
RIGHT_IRIS_CENTER = 473

# Posture Thresholds (Nose to Shoulder distance)
SLOUCH_THRESHOLD = 0.22 

# Color Palette (BGR Format)
COLOR_NEON_GREEN = (0, 255, 127)
COLOR_CYAN       = (255, 255, 0)
COLOR_CORAL_RED  = (71, 99, 255)
COLOR_AMBER      = (0, 165, 255)
COLOR_DARK_BG    = (20, 20, 20)
COLOR_WHITE      = (255, 255, 255)


def get_ai_feedback(focus_time, slouch_count, name):
    """Generates 1-sentence motivational advice using Google Gemini API or Simulation Mode."""
    user_label = name if name.strip() != "" else "Student"
    if not USER_API_KEY or USER_API_KEY == "":
        return f"🌟 [Simulation Mode] Keep going, {user_label}! Focus is good ({int(focus_time)}s). Maintain your posture!"
        
    try:
        genai.configure(api_key=USER_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"A student named {user_label} studied for {int(focus_time)} seconds but slouched {slouch_count} times. Give a 1-sentence motivational advice specifically addressing them."
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        return f"💡 Tip for {user_label}: Keep your spine straight and blink often to reduce eye strain."


class SmartProctorUI:
    """Class to handle modern UI rendering and HUD overlays."""
    
    @staticmethod
    def draw_glass_card(image, pt1, pt2, bg_color=(20, 20, 20), alpha=0.6):
        """Draws a sleek translucent HUD card."""
        overlay = image.copy()
        cv2.rectangle(overlay, pt1, pt2, bg_color, -1)
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
        # Add subtle glowing border
        cv2.rectangle(image, pt1, pt2, (80, 80, 80), 1, cv2.LINE_AA)

    @staticmethod
    def draw_progress_bar(image, pt, size, val, max_val, color):
        """Draws a smooth rounded horizontal progress bar."""
        x, y = pt
        w, h = size
        fill_w = int((val / max_val) * w)
        
        # Background track
        cv2.rectangle(image, (x, y), (x + w, y + h), (50, 50, 50), -1, cv2.LINE_AA)
        # Active progress fill
        if fill_w > 0:
            cv2.rectangle(image, (x, y), (x + fill_w, y + h), color, -1, cv2.LINE_AA)
        # Border
        cv2.rectangle(image, (x, y), (x + w, y + h), (150, 150, 150), 1, cv2.LINE_AA)


class ProctoringEngine:
    def __init__(self):
        # Initialize MediaPipe solutions
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )

        # Gamification & State Metrics
        self.aura_points = 1000.0
        self.focus_streak_sec = 0.0
        self.last_time = time.time()
        self.gaze_state = "Center"
        self.posture_state = "Upright"

        # Slouching tracking
        self.slouch_count = 0
        self.was_slouching = False
        self.ai_advice = "Initializing AI Guidance..."
        self.last_ai_fetch_time = 0

    def calculate_gaze(self, landmarks, img_w, img_h):
        """Calculates horizontal gaze direction (Left, Center, Right)."""
        l_outer = np.array([landmarks[LEFT_EYE_OUTER].x * img_w, landmarks[LEFT_EYE_OUTER].y * img_h])
        l_inner = np.array([landmarks[LEFT_EYE_INNER].x * img_w, landmarks[LEFT_EYE_INNER].y * img_h])
        l_iris  = np.array([landmarks[LEFT_IRIS_CENTER].x * img_w, landmarks[LEFT_IRIS_CENTER].y * img_h])

        total_width = np.linalg.norm(l_outer - l_inner)
        iris_dist = np.linalg.norm(l_iris - l_inner)
        
        if total_width == 0:
            return "Center"

        ratio = iris_dist / total_width

        if ratio < 0.38:
            return "Right"
        elif ratio > 0.62:
            return "Left"
        return "Center"

    def calculate_posture(self, pose_landmarks):
        """Detects slouching based on vertical distance between nose and shoulders."""
        nose = pose_landmarks.landmark[self.mp_pose.PoseLandmark.NOSE]
        l_shoulder = pose_landmarks.landmark[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
        r_shoulder = pose_landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]

        shoulder_y_avg = (l_shoulder.y + r_shoulder.y) / 2.0
        vert_dist = shoulder_y_avg - nose.y

        if vert_dist < SLOUCH_THRESHOLD:
            return "Slouching"
        return "Upright"

    def update_metrics(self, dt, is_focused):
        """Updates live Aura Points and Focus Streak continuously."""
        if is_focused:
            self.focus_streak_sec += dt
            self.aura_points += dt * 2.5  # Gain +2.5 pts/sec while focused
        else:
            self.focus_streak_sec = 0.0
            self.aura_points -= dt * 8.0  # Lose -8.0 pts/sec on distraction

        # Clamp Aura Points
        self.aura_points = max(0.0, min(9999.0, self.aura_points))

        # Track slouch transitions
        is_slouching = (self.posture_state == "Slouching")
        if is_slouching and not self.was_slouching:
            self.slouch_count += 1
        self.was_slouching = is_slouching

        # Fetch AI feedback every 15 seconds
        current_time = time.time()
        if current_time - self.last_ai_fetch_time > 15:
            self.ai_advice = get_ai_feedback(self.focus_streak_sec, self.slouch_count, USER_NAME)
            self.last_ai_fetch_time = current_time

    def process_frame(self, frame):
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time

        h, w, _ = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_results = self.face_mesh.process(rgb_frame)
        pose_results = self.pose.process(rgb_frame)

        self.gaze_state = "Undetected"
        self.posture_state = "Undetected"

        if face_results.multi_face_landmarks:
            landmarks = face_results.multi_face_landmarks[0].landmark
            self.gaze_state = self.calculate_gaze(landmarks, w, h)

        if pose_results.pose_landmarks:
            self.posture_state = self.calculate_posture(pose_results.pose_landmarks)

        is_focused = (self.gaze_state == "Center") and (self.posture_state == "Upright")
        self.update_metrics(dt, is_focused)

        self.render_hud(frame, is_focused)
        
        return frame

    def render_hud(self, frame, is_focused):
        """Applies the modern futuristic overlay components on the feed."""
        h, w, _ = frame.shape

        # Top Glass Dashboard Panel
        SmartProctorUI.draw_glass_card(frame, (20, 20), (w - 20, 110), bg_color=(15, 15, 15), alpha=0.7)

        # Title / Header with User Name
        user_display = f" | User: {USER_NAME}" if USER_NAME.strip() else ""
        cv2.putText(frame, f"AI SMART CLASSROOM PROCTOR{user_display}", (40, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_CYAN, 2, cv2.LINE_AA)

        # Live Status Indicator Badge
        status_text = "FOCUSED" if is_focused else "DISTRACTED / ALERT"
        badge_color = COLOR_NEON_GREEN if is_focused else COLOR_CORAL_RED
        cv2.rectangle(frame, (w - 230, 32), (w - 40, 62), badge_color, -1, cv2.LINE_AA)
        cv2.putText(frame, status_text, (w - 220, 53), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2, cv2.LINE_AA)

        # Real-time Metrics (Gaze & Posture & Slouch count)
        gaze_color = COLOR_NEON_GREEN if self.gaze_state == "Center" else COLOR_AMBER
        posture_color = COLOR_NEON_GREEN if self.posture_state == "Upright" else COLOR_CORAL_RED

        cv2.putText(frame, f"Gaze: {self.gaze_state}", (40, 85), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, gaze_color, 1, cv2.LINE_AA)
        cv2.putText(frame, f"Posture: {self.posture_state}", (200, 85), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, posture_color, 1, cv2.LINE_AA)
        cv2.putText(frame, f"Slouches: {self.slouch_count}", (420, 85), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_AMBER, 1, cv2.LINE_AA)

        # Bottom HUD Panel (Streak, Live Aura Points, and AI Advice)
        SmartProctorUI.draw_glass_card(frame, (20, h - 110), (w - 20, h - 20), bg_color=(15, 15, 15), alpha=0.75)

        # Live Aura Points Display
        aura_str = f"AURA: {int(self.aura_points):04d} pts"
        cv2.putText(frame, aura_str, (40, h - 65), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_NEON_GREEN, 2, cv2.LINE_AA)

        # AI Advice Banner at bottom
        cv2.putText(frame, f"AI Tip: {self.ai_advice}", (40, h - 35), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_CYAN, 1, cv2.LINE_AA)

        # Live Focus Streak Progress Bar
        streak_str = f"Streak: {int(self.focus_streak_sec)}s"
        cv2.putText(frame, streak_str, (w - 320, h - 75), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_WHITE, 1, cv2.LINE_AA)
        
        SmartProctorUI.draw_progress_bar(
            frame, 
            pt=(w - 320, h - 60), 
            size=(280, 15), 
            val=min(self.focus_streak_sec, 60.0), 
            max_val=60.0, 
            color=COLOR_CYAN
        )


def main():
    cap = cv2.VideoCapture(0)
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    proctor = ProctoringEngine()

    print("[INFO] Starting AI Proctoring Feed... Press 'q' to quit.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Camera frame unavailable.")
            break

        frame = cv2.flip(frame, 1)
        frame = proctor.process_frame(frame)

        cv2.imshow("AI Smart Classroom Proctoring System", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
